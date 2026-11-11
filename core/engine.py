"""
Discrete-Event Simulation Engine for single-class FIFO and multi-class priority queues.
"""

import math
import heapq
import random
import time
from collections import deque, defaultdict
from typing import List, Dict, Optional

from .constants import PRIORITY_NAMES, to_subscript
from .distributions import Distribution, ExponentialDist
from .entities import Customer, Server


class QueueSimEngine:
    def __init__(
        self,
        n_servers: int = 1,
        queue_capacity: float = 12,
        service_dist: Optional[Distribution] = None,
        arrival_dists: Optional[Dict[int, Distribution]] = None,
        priority_enabled: bool = False,
        seed: Optional[int] = None,
    ):
        if seed is not None:
            random.seed(seed)

        if (isinstance(n_servers, str) and n_servers.lower() == 'inf') or math.isinf(n_servers):
            self.c = math.inf
        else:
            self.c = max(1, int(n_servers))

        if (isinstance(queue_capacity, str) and queue_capacity.lower() == 'inf') or math.isinf(queue_capacity):
            self.K = math.inf
        else:
            self.K = max(0, int(queue_capacity))
        self.priority_enabled = bool(priority_enabled)

        self.service_dist = service_dist or ExponentialDist(rate=1.0)
        if arrival_dists is not None:
            self.arrival_dists = arrival_dists
        else:
            if not self.priority_enabled:
                self.arrival_dists = {-1: ExponentialDist(rate=0.8)}
            else:
                self.arrival_dists = {
                    0: ExponentialDist(rate=0.3),
                    1: ExponentialDist(rate=0.3),
                    2: ExponentialDist(rate=0.2),
                }

        self.reset()

    def reset(self):
        self.current_time = 0.0
        self.last_event_time = 0.0
        self.event_counter = 0

        self.event_heap = []
        if math.isinf(self.c):
            self.servers = [Server(id=i) for i in range(5)]
        else:
            self.servers = [Server(id=i) for i in range(self.c)]
        self.queues = defaultdict(deque)

        self.next_customer_id = 1
        self.customers_arrived_total = 0
        self.customers_arrived_by_prio = defaultdict(int)

        self.customers_dropped_total = 0
        self.customers_dropped_by_prio = defaultdict(int)

        self.customers_served_total = 0
        self.customers_served_by_prio = defaultdict(int)

        self.total_system_time = 0.0
        self.total_waiting_time = 0.0
        self.total_waiting_time_by_prio = defaultdict(float)

        self.completed_customers = deque(maxlen=5000)
        self.recent_drops = deque(maxlen=30)

        self.retired_busy_time = 0.0
        self.server_capacity_integral = 0.0

        self.state_durations = defaultdict(float)
        self.queue_state_durations = defaultdict(float)

        self.time_history = deque([0.0], maxlen=1000)
        self.occupancy_history = deque([0], maxlen=1000)
        self.queue_len_history = deque([0], maxlen=1000)
        self.drop_count_history = deque([0], maxlen=1000)

        self.event_log = deque(maxlen=200)

        self.last_arrival_wall_time = 0.0
        self.last_arrival_prio = -1
        self.last_arrival_id = None
        self.last_arrival_dropped = False

        self.ensure_arrival_events_scheduled()

    @staticmethod
    def _is_dist_different(d1: Optional[Distribution], d2: Optional[Distribution]) -> bool:
        if (d1 is None) != (d2 is None):
            return True
        if d1 is None and d2 is None:
            return False
        return d1.name != d2.name or d1.params != d2.params

    def ensure_arrival_events_scheduled(self):
        """Ensure every active arrival stream has at least one scheduled event in event_heap."""
        scheduled_prios = {payload for (t, c, ev_type, payload) in self.event_heap if ev_type == 'arrival'}
        for prio, dist in self.arrival_dists.items():
            if dist is not None and prio not in scheduled_prios:
                next_t = self.current_time + max(0.0, dist.sample())
                self._schedule_event(next_t, 'arrival', prio)

    def sync_arrival_streams(self, new_arrival_dists: Dict[int, Distribution]):
        """Synchronize active arrival streams dynamically without freezing or dropping events.
        Purges scheduled arrivals for removed streams, immediately reschedules arrival events whose
        distribution parameters have changed so new rates take effect without lag, and ensures all
        active streams have scheduled arrivals."""
        changed_prios = set()
        for prio, new_d in new_arrival_dists.items():
            old_d = self.arrival_dists.get(prio)
            if self._is_dist_different(old_d, new_d):
                changed_prios.add(prio)

        valid_heap = []
        for item in self.event_heap:
            t, c, ev_type, payload = item
            if ev_type == 'arrival':
                if payload in new_arrival_dists and payload not in changed_prios and new_arrival_dists[payload] is not None:
                    valid_heap.append(item)
            else:
                valid_heap.append(item)
        heapq.heapify(valid_heap)
        self.event_heap = valid_heap
        self.arrival_dists = new_arrival_dists
        self.ensure_arrival_events_scheduled()

    def sync_service_dist(self, new_serv_dist: Distribution):
        """Update service distribution and unfreeze any departures scheduled at inf."""
        old_mean = self.service_dist.mean() if self.service_dist else 1.0
        self.service_dist = new_serv_dist
        new_mean = new_serv_dist.mean()
        if math.isinf(old_mean) and not math.isinf(new_mean):
            new_heap = []
            inf_departures = set()
            for item in self.event_heap:
                t, c, ev_type, payload = item
                if ev_type == 'departure' and math.isinf(t):
                    inf_departures.add(payload)
                else:
                    new_heap.append(item)
            heapq.heapify(new_heap)
            self.event_heap = new_heap
            for s_id in inf_departures:
                if s_id < len(self.servers):
                    srv = self.servers[s_id]
                    if srv.is_busy and srv.current_customer:
                        serv_dur = max(1e-6, self.service_dist.sample())
                        depart_t = self.current_time + serv_dur
                        self._schedule_event(depart_t, 'departure', srv.id)

    def _schedule_event(self, time: float, ev_type: str, payload):
        self.event_counter += 1
        heapq.heappush(self.event_heap, (time, self.event_counter, ev_type, payload))

    @property
    def total_in_queue(self) -> int:
        return sum(len(q) for q in self.queues.values())

    @property
    def busy_servers_count(self) -> int:
        return sum(1 for s in self.servers if s.is_busy)

    @property
    def total_in_system(self) -> int:
        return self.busy_servers_count + self.total_in_queue

    def _accumulate_time(self, new_time: float):
        dt = new_time - self.last_event_time
        if dt > 0:
            self.state_durations[self.total_in_system] += dt
            self.queue_state_durations[self.total_in_queue] += dt
            if not math.isinf(self.c):
                self.server_capacity_integral += self.c * dt
        self.last_event_time = new_time

    def step(self) -> Optional[dict]:
        # Self-healing guard: ensure active arrival streams always have scheduled arrival events
        if not any(ev_type == 'arrival' for (_, _, ev_type, _) in self.event_heap):
            self.ensure_arrival_events_scheduled()

        if not self.event_heap or math.isinf(self.event_heap[0][0]):
            return None

        event_time, _, ev_type, payload = heapq.heappop(self.event_heap)

        self._accumulate_time(event_time)
        self.current_time = event_time

        event_info = None

        if ev_type == 'arrival':
            prio = payload
            event_info = self._handle_arrival(prio)
        elif ev_type == 'departure':
            server_idx = payload
            event_info = self._handle_departure(server_idx)

        self.time_history.append(self.current_time)
        self.occupancy_history.append(self.total_in_system)
        self.queue_len_history.append(self.total_in_queue)
        self.drop_count_history.append(self.customers_dropped_total)

        if event_info:
            self.event_log.append(event_info)

        return event_info

    def _pop_next_waiting_customer(self) -> Optional[Customer]:
        if self.priority_enabled:
            for p in (0, 1, 2):
                if self.queues[p]:
                    return self.queues[p].popleft()
            if self.queues[-1]:
                return self.queues[-1].popleft()
        else:
            if self.queues[-1]:
                return self.queues[-1].popleft()
            for p in (0, 1, 2):
                if self.queues[p]:
                    return self.queues[p].popleft()
        return None

    def _dispatch_customer_to_server(self, cust: Customer, server: Server) -> dict:
        serv_dur = max(1e-6, self.service_dist.sample())
        cust.service_start_time = self.current_time
        cust.service_duration = serv_dur
        cust.server_idx = server.id

        server.current_customer = cust
        server.busy_start_time = self.current_time

        depart_t = self.current_time + serv_dur
        self._schedule_event(depart_t, 'departure', server.id)

        p_label = f" (Prio: {PRIORITY_NAMES[cust.priority]})" if self.priority_enabled else ""
        ev_dict = {
            'time': self.current_time,
            'type': 'QUEUE_TO_SERVICE',
            'customer': cust,
            'server_id': server.id,
            'prio': cust.priority,
            'msg': f"Dispatched: Cust #{cust.id}{p_label} from Queue -> Server {server.id+1}",
        }
        self.event_log.append(ev_dict)
        return ev_dict

    def assign_idle_servers(self) -> List[dict]:
        """Dispatch any idle servers to pull waiting customers in strict priority order.
        Returns a list of event info dictionaries for assigned customers."""
        events = []
        for server in self.servers:
            if not server.is_busy:
                next_cust = self._pop_next_waiting_customer()
                if next_cust is not None:
                    ev_dict = self._dispatch_customer_to_server(next_cust, server)
                    events.append(ev_dict)

        if math.isinf(self.c):
            while self.total_in_queue > 0:
                next_cust = self._pop_next_waiting_customer()
                if next_cust is None:
                    break
                server = Server(id=len(self.servers))
                self.servers.append(server)
                ev_dict = self._dispatch_customer_to_server(next_cust, server)
                events.append(ev_dict)

        return events

    def _handle_arrival(self, prio: int) -> dict:
        dist = self.arrival_dists.get(prio)
        if dist is not None:
            next_t = self.current_time + max(0.0, dist.sample())
            self._schedule_event(next_t, 'arrival', prio)

        cust = Customer(
            id=self.next_customer_id,
            priority=prio if self.priority_enabled else -1,
            arrival_time=self.current_time,
        )
        self.next_customer_id += 1
        self.customers_arrived_total += 1
        self.customers_arrived_by_prio[cust.priority] += 1

        self.last_arrival_wall_time = time.time()
        self.last_arrival_prio = cust.priority
        self.last_arrival_id = cust.id
        self.last_arrival_dropped = False

        idle_server = next((s for s in self.servers if not s.is_busy), None)
        if idle_server is None and math.isinf(self.c):
            idle_server = Server(id=len(self.servers))
            self.servers.append(idle_server)

        # Only admit directly to an idle server if no customers are already waiting in queue (or ample servers)
        if idle_server is not None and (self.total_in_queue == 0 or math.isinf(self.c)):
            serv_dur = max(1e-6, self.service_dist.sample())
            cust.service_start_time = self.current_time
            cust.service_duration = serv_dur
            cust.server_idx = idle_server.id

            idle_server.current_customer = cust
            idle_server.busy_start_time = self.current_time

            depart_t = self.current_time + serv_dur
            self._schedule_event(depart_t, 'departure', idle_server.id)

            p_label = f" (Prio: {PRIORITY_NAMES[cust.priority]})" if self.priority_enabled else ""
            return {
                'time': self.current_time,
                'type': 'ARRIVAL_TO_SERVICE',
                'customer': cust,
                'server_id': idle_server.id,
                'prio': cust.priority,
                'msg': f"Arrival: Cust #{cust.id}{p_label} -> Assigned to Server {idle_server.id+1}",
            }

        queue_key = cust.priority if self.priority_enabled else -1
        # In Priority Queuing, each traffic type has its own individual queue of capacity K.
        # In Single-Class FIFO, there is a single queue of capacity K.
        q_len = len(self.queues[queue_key])

        if q_len < self.K:
            self.queues[queue_key].append(cust)

            # If an idle server was available, immediately dispatch the highest priority waiting customer
            if idle_server is not None:
                self.assign_idle_servers()

            p_label = f" (Prio: {PRIORITY_NAMES[cust.priority]})" if self.priority_enabled else ""
            q_name = f"Queue P{to_subscript(cust.priority)}" if self.priority_enabled else "Queue"
            k_str = "inf" if math.isinf(self.K) else str(self.K)
            return {
                'time': self.current_time,
                'type': 'ENQUEUE',
                'customer': cust,
                'server_id': None,
                'prio': cust.priority,
                'msg': f"Enqueued: Cust #{cust.id}{p_label} -> {q_name} (Waiting: {len(self.queues[queue_key])}/{k_str})",
            }
        else:
            cust.dropped = True
            self.last_arrival_dropped = True
            self.customers_dropped_total += 1
            self.customers_dropped_by_prio[cust.priority] += 1
            self.recent_drops.append(cust)

            if idle_server is not None:
                self.assign_idle_servers()

            p_label = f" (Prio: {PRIORITY_NAMES[cust.priority]})" if self.priority_enabled else ""
            q_name = f"Queue P{to_subscript(cust.priority)}" if self.priority_enabled else "Buffer"
            k_str = "inf" if math.isinf(self.K) else str(self.K)
            return {
                'time': self.current_time,
                'type': 'DROP',
                'customer': cust,
                'server_id': None,
                'prio': cust.priority,
                'msg': f"REJECTED: Cust #{cust.id}{p_label} -> {q_name} Full (K={k_str})",
            }

    def _handle_departure(self, server_idx: int) -> Optional[dict]:
        if server_idx >= len(self.servers):
            return None
        server = self.servers[server_idx]
        departing_cust = server.current_customer

        if departing_cust is not None:
            departing_cust.departure_time = self.current_time
            self.total_system_time += departing_cust.system_time
            self.total_waiting_time += departing_cust.waiting_time
            self.total_waiting_time_by_prio[departing_cust.priority] += departing_cust.waiting_time
            self.completed_customers.append(departing_cust)

            self.customers_served_total += 1
            self.customers_served_by_prio[departing_cust.priority] += 1
            server.customers_served += 1

            server.last_departure_wall_time = time.time()
            server.last_departed_customer_id = departing_cust.id

            if server.busy_start_time is not None:
                server.total_busy_time += (self.current_time - server.busy_start_time)
                server.busy_start_time = None

            server.current_customer = None

        next_cust = self._pop_next_waiting_customer()

        if next_cust is not None:
            serv_dur = max(1e-6, self.service_dist.sample())
            next_cust.service_start_time = self.current_time
            next_cust.service_duration = serv_dur
            next_cust.server_idx = server.id

            server.current_customer = next_cust
            server.busy_start_time = self.current_time

            depart_t = self.current_time + serv_dur
            self._schedule_event(depart_t, 'departure', server.id)

            return {
                'time': self.current_time,
                'type': 'DEPARTURE_AND_NEXT',
                'customer': departing_cust,
                'next_customer': next_cust,
                'server_id': server.id,
                'prio': next_cust.priority if next_cust else -1,
                'departing_prio': departing_cust.priority if departing_cust else -1,
                'msg': f"Departure: Cust #{departing_cust.id} left. Server {server.id+1} starts Cust #{next_cust.id}",
            }
        else:
            if math.isinf(self.c):
                while len(self.servers) > 5 and not self.servers[-1].is_busy:
                    popped_srv = self.servers.pop()
                    self.retired_busy_time += popped_srv.total_busy_time

            return {
                'time': self.current_time,
                'type': 'DEPARTURE_IDLE',
                'customer': departing_cust,
                'server_id': server.id,
                'prio': departing_cust.priority if departing_cust else -1,
                'msg': f"Departure: Cust #{departing_cust.id} left. Server {server.id+1} is IDLE",
            }

    def run_batch(self, max_events: int = 10000, target_time: Optional[float] = None):
        count = 0
        while self.event_heap and count < max_events:
            if target_time is not None and self.current_time >= target_time:
                break
            self.step()
            count += 1

    def get_metrics(self) -> dict:
        T = max(1e-6, self.current_time)

        total_time_accum = sum(self.state_durations.values())
        if total_time_accum > 0:
            L_emp = sum(n * dt for n, dt in self.state_durations.items()) / total_time_accum
            Lq_emp = sum(n * dt for n, dt in self.queue_state_durations.items()) / total_time_accum
        else:
            L_emp = 0.0
            Lq_emp = 0.0

        busy_time = self.retired_busy_time + sum(s.total_busy_time for s in self.servers)
        for s in self.servers:
            if s.is_busy and s.busy_start_time is not None:
                busy_time += (self.current_time - s.busy_start_time)

        if math.isinf(self.c):
            rho_emp = 0.0
        else:
            denom = self.server_capacity_integral if self.server_capacity_integral > 0 else (self.c * T)
            rho_emp = (busy_time / denom) if denom > 0 else 0.0

        W_emp = (self.total_system_time / self.customers_served_total) if self.customers_served_total > 0 else 0.0
        Wq_emp = (self.total_waiting_time / self.customers_served_total) if self.customers_served_total > 0 else 0.0

        Wq_prio = {}
        for p in (-1, 0, 1, 2):
            served_p = self.customers_served_by_prio[p]
            Wq_prio[p] = (self.total_waiting_time_by_prio[p] / served_p) if served_p > 0 else 0.0

        admitted = self.customers_arrived_total - self.customers_dropped_total
        lambda_eff = admitted / T
        lambda_total = self.customers_arrived_total / T

        p_loss_emp = (
            (self.customers_dropped_total / self.customers_arrived_total)
            if self.customers_arrived_total > 0
            else 0.0
        )
        p_loss_prio = {}
        for p in (-1, 0, 1, 2):
            arr_p = self.customers_arrived_by_prio[p]
            drop_p = self.customers_dropped_by_prio[p]
            p_loss_prio[p] = (drop_p / arr_p) if arr_p > 0 else 0.0

        littles_L = lambda_eff * W_emp
        littles_Lq = lambda_eff * Wq_emp
        littles_error_L = abs(L_emp - littles_L)

        max_state = max(list(self.state_durations.keys()) + [0])
        p_n_emp = {
            n: (self.state_durations[n] / total_time_accum) if total_time_accum > 0 else 0.0
            for n in range(max_state + 1)
        }

        return {
            'T': T,
            'L': L_emp,
            'Lq': Lq_emp,
            'W': W_emp,
            'Wq': Wq_emp,
            'Wq_prio': Wq_prio,
            'rho': rho_emp,
            'lambda_total': lambda_total,
            'lambda_eff': lambda_eff,
            'p_loss': p_loss_emp,
            'p_loss_prio': p_loss_prio,
            'littles_L': littles_L,
            'littles_Lq': littles_Lq,
            'littles_error_L': littles_error_L,
            'p_n': p_n_emp,
            'arrived': self.customers_arrived_total,
            'served': self.customers_served_total,
            'dropped': self.customers_dropped_total,
            # Slideset aliases (Cerroni notation)
            'A': L_emp,
            'A_c': Lq_emp,
            'A_s': (busy_time / T) if T > 0 else 0.0,
            'delta_bar': W_emp,
            'eta_bar': Wq_emp,
            'pi_p': p_loss_emp,
            'lambda_s': lambda_eff,
            'lambda_p': (self.customers_dropped_total / T) if T > 0 else 0.0,
            'littles_error_A': littles_error_L,
        }