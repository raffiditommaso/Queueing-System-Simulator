"""
Customer and Server entity models for the Queueing System Simulator.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    id: int
    priority: int                   # -1 = Standard FIFO, 0 = High, 1 = Med, 2 = Low
    arrival_time: float
    service_duration: float = 0.0
    service_start_time: Optional[float] = None
    departure_time: Optional[float] = None
    server_idx: Optional[int] = None
    dropped: bool = False

    @property
    def waiting_time(self) -> float:
        if self.service_start_time is not None:
            return self.service_start_time - self.arrival_time
        return 0.0

    @property
    def system_time(self) -> float:
        if self.departure_time is not None:
            return self.departure_time - self.arrival_time
        return 0.0


@dataclass
class Server:
    id: int
    current_customer: Optional[Customer] = None
    total_busy_time: float = 0.0
    busy_start_time: Optional[float] = None
    customers_served: int = 0
    last_departure_wall_time: float = 0.0
    last_departed_customer_id: Optional[int] = None

    @property
    def is_busy(self) -> bool:
        return self.current_customer is not None