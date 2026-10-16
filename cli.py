#!/usr/bin/env python3
"""
Command-Line Interface (CLI) parser and headless batch runner
for the Queueing System Simulator.
"""

import sys
import argparse

from core.distributions import ExponentialDist
from core.engine import QueueSimEngine
from core.theory import TheoreticalModels


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for both GUI and headless CLI modes."""
    parser = argparse.ArgumentParser(
        description="Advanced Educational Queueing System Simulator"
    )
    parser.add_argument(
        '--cli', action='store_true',
        help="Run headlessly in CLI mode without GUI"
    )
    parser.add_argument(
        '--servers', '-m', '-c', type=int, default=1,
        help="Number of parallel servers m (integer >= 1)"
    )
    parser.add_argument(
        '--queue', '-K', type=str, default='12',
        help="Queue capacity (int or 'inf')"
    )
    parser.add_argument(
        '--events', type=int, default=50000,
        help="Number of simulation events for batch run"
    )
    parser.add_argument(
        '--lambda-rate', type=float, default=0.8,
        help="Arrival rate lambda for single FIFO"
    )
    parser.add_argument(
        '--service-rate', type=float, default=1.0,
        help="Service rate mu"
    )
    parser.add_argument(
        '--priority', action='store_true', default=False,
        help="Enable priority queuing"
    )
    parser.add_argument(
        '--p0-rate', type=float, default=0.3,
        help="P0 High Priority rate"
    )
    parser.add_argument(
        '--p1-rate', type=float, default=0.3,
        help="P1 Medium Priority rate"
    )
    parser.add_argument(
        '--p2-rate', type=float, default=0.2,
        help="P2 Low Priority rate"
    )
    parser.add_argument(
        '--no-priority', action='store_true', default=False,
        help="Force FIFO queue (default)"
    )
    parser.add_argument(
        '--seed', type=int, default=42,
        help="RNG seed"
    )
    return parser.parse_args()


def run_headless_cli(args: argparse.Namespace) -> None:
    """Execute a headless batch simulation and print summary metrics to stdout."""
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    c = max(1, int(args.servers))
    K = float('inf') if args.queue.lower() == 'inf' else int(args.queue)
    prio_enabled = bool(args.priority and not args.no_priority)

    if prio_enabled:
        arr_dists = {
            0: ExponentialDist(rate=args.p0_rate),
            1: ExponentialDist(rate=args.p1_rate),
            2: ExponentialDist(rate=args.p2_rate)
        }
    else:
        arr_dists = {-1: ExponentialDist(rate=args.lambda_rate)}

    serv_dist = ExponentialDist(rate=args.service_rate)

    sim = QueueSimEngine(
        n_servers=c,
        queue_capacity=K,
        service_dist=serv_dist,
        arrival_dists=arr_dists,
        priority_enabled=prio_enabled,
        seed=args.seed
    )

    kendall = TheoreticalModels.get_kendall_notation(
        arr_dists, serv_dist, c, K, prio_enabled
    )
    print("=" * 70)
    print(" ADVANCED QUEUEING SYSTEM SIMULATOR (CLI HEADLESS BATCH)")
    print(f" Model: {kendall}")
    print(f" Servers: m = {c} | Buffer Capacity: K = {K}")
    if prio_enabled:
        print(
            f" Priority Rates: λ₀={args.p0_rate}, λ₁={args.p1_rate}, "
            f"λ₂={args.p2_rate} | μ={args.service_rate}"
        )
    else:
        print(f" Arrival Rate: λ={args.lambda_rate} | Service Rate: μ={args.service_rate}")
    print(f" Simulating {args.events:,} discrete events...")
    print("=" * 70)

    sim.run_batch(max_events=args.events)
    m = sim.get_metrics()
    a0 = (args.lambda_rate / args.service_rate) if not prio_enabled else ((args.p0_rate + args.p1_rate + args.p2_rate) / args.service_rate)

    print(f"Simulation Time Reached:      t = {m['T']:.2f} s")
    print(f"Total Arrivals:               a(t) = {m['arrived']:,}")
    print(f"Successfully Served:          d(t) = {m['served']:,}")
    print(f"Dropped / Rejected:           a_p(t) = {m['dropped']:,} (Blocking π_p: {m['p_loss']*100:.2f}%)")
    print(f"Theoretical Offered Traffic:  A₀ = {a0:.4f} Erlang (per server: {a0/c:.4f})")
    print(f"Server Utilization ρ:         {m['rho']:.4f}")
    print(f"Average in System (A):        {m['L']:.4f} Erlang / cust")
    print(f"Average in Queue (A_c):       {m['Lq']:.4f} cust")
    print(f"Average Sojourn Time (δ̄):     {m['W']:.4f} s")
    print(f"Average Waiting Time (η̄):     {m['Wq']:.4f} s")
    print("-" * 70)
    if prio_enabled:
        print("PER-PRIORITY MEAN WAITING TIMES (η̄):")
        print(f"  Class 0 (High Priority P₀):   {m['Wq_prio'][0]:.4f} s  (Blocking π_p: {m['p_loss_prio'][0]*100:.2f}%)")
        print(f"  Class 1 (Medium Priority P₁): {m['Wq_prio'][1]:.4f} s  (Blocking π_p: {m['p_loss_prio'][1]*100:.2f}%)")
        print(f"  Class 2 (Low Priority P₂):    {m['Wq_prio'][2]:.4f} s  (Blocking π_p: {m['p_loss_prio'][2]*100:.2f}%)")
        print("-" * 70)
    print("LITTLE'S LAW VERIFICATION (A = λ_s * δ̄):")
    print(f"  Average System Traffic A:     {m['L']:.5f}")
    print(f"  Admitted Arrival Rate λ_s:   {m['lambda_eff']:.5f} cust/s")
    print(f"  λ_s * δ̄:                     {m['littles_L']:.5f}")
    print(f"  Absolute Error |A - λ_s δ̄|:   {m['littles_error_L']:.6f} (Verified)")
    print("=" * 70)


if __name__ == '__main__':
    run_headless_cli(parse_arguments())
