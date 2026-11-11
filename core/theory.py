"""
Analytical queueing theory models (Kendall notation, M/M/c, M/M/c/K, and M/G/1).
"""

import math
from typing import Dict
from .distributions import Distribution


class TheoreticalModels:
    @staticmethod
    def get_kendall_notation(
        arrival_dists: Dict[int, Distribution],
        service_dist: Distribution,
        c: float,
        K: float,
        priority: bool,
    ) -> str:
        syms = set(d.kendall_symbol() for d in arrival_dists.values() if d is not None)
        arr_sym = list(syms)[0] if len(syms) == 1 else 'G'
        serv_sym = service_dist.kendall_symbol()
        c_str = 'inf' if math.isinf(c) else str(int(c))

        # Kendall Notation A/B/m/n/p/S (Slide 15-16 of 03-Traffic):
        # m = number of servers
        # n = size of the queue (maximum number of customers that queuing space can hold)
        # S = queuing policy (FIFO, PRIO)
        # When queue buffer is infinite (K = inf), n is omitted in standard short form (e.g. M/M/m).
        # When finite, n = K (e.g. M/M/m/0 for Erlang-B pure loss system, M/M/1/12 for finite buffer).
        if math.isinf(K):
            if priority:
                return f"{arr_sym}/{serv_sym}/{c_str}/PRIO"
            else:
                return f"{arr_sym}/{serv_sym}/{c_str}"
        else:
            n_str = f"3x{int(K)}" if priority else str(int(K))
            prio_str = "/PRIO" if priority else ""
            return f"{arr_sym}/{serv_sym}/{c_str}/{n_str}{prio_str}"

    @staticmethod
    def solve_mminf(lam: float, mu: float) -> dict:
        """Analytical solution for M/M/inf (Ample servers, pure delay system)."""
        if lam <= 0 or mu <= 0:
            return {}
        a = lam / mu
        p0 = math.exp(-a) if a < 700 else 0.0
        p_n = {}
        max_n = max(25, int(a + 4 * math.sqrt(max(1.0, a))))
        cur_p = p0
        p_n[0] = cur_p
        for n in range(1, max_n + 1):
            cur_p = cur_p * (a / n)
            p_n[n] = cur_p

        L = a
        Lq = 0.0
        W = 1.0 / mu
        Wq = 0.0

        return {
            'rho': 0.0,
            'rho_offered': 0.0,
            'A_0': a,
            'p0': p0,
            'p_c': 0.0,
            'L': L,
            'Lq': Lq,
            'W': W,
            'Wq': Wq,
            'p_loss': 0.0,
            'p_n': p_n,
            'unstable': False,
            # Slideset aliases (Cerroni notation)
            'A': L,
            'A_c': Lq,
            'A_s': a,
            'A_p': 0.0,
            'delta_bar': W,
            'eta_bar': Wq,
            'theta_bar': 1.0 / mu,
            'epsilon_bar': 0.0,
            'pi_p': 0.0,
            'pi_r': 0.0,
            'lambda_s': lam,
            'lambda_p': 0.0,
        }

    @staticmethod
    def solve_mmc_infinite(lam: float, mu: float, c: float) -> dict:
        if math.isinf(c):
            return TheoreticalModels.solve_mminf(lam, mu)
        c = int(c)
        if lam <= 0 or mu <= 0:
            return {}
        a = lam / mu
        rho = a / c
        if rho >= 1.0:
            return {'unstable': True, 'rho': 1.0, 'rho_offered': rho, 'A_0': a}

        # Stable ratio recurrence: t_0 = 1.0, t_n = t_{n-1} * (a / n)
        t = 1.0
        sum_terms = 1.0
        for n in range(1, c):
            t *= (a / n)
            sum_terms += t

        t_c = t * (a / c)
        c_term = t_c / (1.0 - rho)
        p0 = 1.0 / (sum_terms + c_term)
        p_c = c_term * p0

        Lq = p_c * rho / (1.0 - rho)
        Wq = Lq / lam
        W = Wq + 1.0 / mu
        L = Lq + a

        p_n = {}
        p_cur = p0
        p_n[0] = p_cur
        for n in range(1, c + 1):
            p_cur *= (a / n)
            p_n[n] = p_cur
        for n in range(c + 1, min(c + 50, 2000)):
            p_cur *= rho
            p_n[n] = p_cur

        return {
            'rho': rho,
            'rho_offered': rho,
            'A_0': a,
            'p0': p0,
            'p_c': p_c,
            'L': L,
            'Lq': Lq,
            'W': W,
            'Wq': Wq,
            'p_loss': 0.0,
            'p_n': p_n,
            'unstable': False,
            # Slideset aliases (Cerroni notation)
            'A': L,
            'A_c': Lq,
            'A_s': a,
            'A_p': 0.0,
            'delta_bar': W,
            'eta_bar': Wq,
            'theta_bar': 1.0 / mu,
            'epsilon_bar': (1.0 / mu) / (c - a),
            'pi_p': 0.0,
            'pi_r': p_c,
            'lambda_s': lam,
            'lambda_p': 0.0,
        }

    @staticmethod
    def solve_mmc_finite(lam: float, mu: float, c: float, K_queue: int) -> dict:
        if math.isinf(c):
            return TheoreticalModels.solve_mminf(lam, mu)
        c = int(c)
        K_queue = int(K_queue)
        if lam <= 0 or mu <= 0:
            return {}
        K_sys = c + K_queue
        a = lam / mu
        rho_offered = a / c

        # Terms for n = 0 to c: t_n = (a^n) / n!
        t = 1.0
        sum_terms = 1.0
        for n in range(1, c + 1):
            t *= (a / n)
            sum_terms += t
        t_c = t

        # Queue tail sum: sum_{j=1}^{K_queue} rho^j
        if K_queue > 0:
            if abs(rho_offered - 1.0) < 1e-12:
                sum_tail = float(K_queue)
                sum_j_tail = float(K_queue * (K_queue + 1)) / 2.0
                rho_to_kq = 1.0
            else:
                ln_rho = math.log(rho_offered) if rho_offered > 0 else -100.0
                if K_queue * ln_rho > 700.0:
                    rho_to_kq = float('inf')
                else:
                    rho_to_kq = rho_offered ** K_queue

                if math.isinf(rho_to_kq):
                    p0 = 0.0
                    p_loss = 1.0 - (1.0 / rho_offered)
                    lambda_eff = lam * (1.0 - p_loss)
                    rho_carried = lambda_eff / (c * mu)
                    Lq = float(K_queue)
                    L = c + Lq
                    W = L / lambda_eff if lambda_eff > 0 else 0.0
                    Wq = Lq / lambda_eff if lambda_eff > 0 else 0.0
                    return {
                        'rho': rho_carried,
                        'rho_offered': rho_offered,
                        'A_0': a,
                        'p0': 0.0,
                        'L': L,
                        'Lq': Lq,
                        'W': W,
                        'Wq': Wq,
                        'p_loss': p_loss,
                        'lambda_eff': lambda_eff,
                        'p_n': {0: 0.0},
                        'unstable': False,
                        # Slideset aliases (Cerroni notation)
                        'A': L,
                        'A_c': Lq,
                        'A_s': (1.0 - p_loss) * a,
                        'A_p': p_loss * a,
                        'delta_bar': W,
                        'eta_bar': Wq,
                        'theta_bar': 1.0 / mu,
                        'epsilon_bar': 0.0,
                        'pi_p': p_loss,
                        'pi_r': 0.0,
                        'lambda_s': lambda_eff,
                        'lambda_p': lam * p_loss,
                    }

                sum_tail = rho_offered * (1.0 - rho_to_kq) / (1.0 - rho_offered)
                sum_j_tail = (rho_offered / ((1.0 - rho_offered) ** 2)) * (
                    1.0 - (K_queue + 1) * rho_to_kq + K_queue * rho_to_kq * rho_offered
                )
            sum_coeffs = sum_terms + t_c * sum_tail
            p0 = 1.0 / sum_coeffs
            p_loss = p0 * t_c * rho_to_kq
            Lq = p0 * t_c * sum_j_tail
            # Congestion probability pi_r = sum_{k=c}^{c+K_queue-1} P_k (Slide 47 of 05-ErlangFormulas)
            if abs(rho_offered - 1.0) < 1e-12:
                sum_pi_r = float(K_queue)
            else:
                sum_pi_r = (1.0 - rho_to_kq) / (1.0 - rho_offered)
            pi_r = p0 * t_c * sum_pi_r
        else:
            p0 = 1.0 / sum_terms
            p_loss = p0 * t_c
            Lq = 0.0
            pi_r = 0.0

        lambda_eff = lam * (1.0 - p_loss)
        rho_carried = lambda_eff / (c * mu)
        Ls = lambda_eff / mu
        L = Ls + Lq
        W = L / lambda_eff if lambda_eff > 0 else 0.0
        Wq = Lq / lambda_eff if lambda_eff > 0 else 0.0
        epsilon_bar = (Wq / pi_r) if pi_r > 0 else 0.0

        p_n = {}
        p_cur = p0
        p_n[0] = p_cur
        limit_n = min(K_sys, max(25, c + 20))
        for n in range(1, min(c, limit_n) + 1):
            p_cur *= (a / n)
            p_n[n] = p_cur
        for n in range(c + 1, limit_n + 1):
            p_cur *= rho_offered
            p_n[n] = p_cur

        return {
            'rho': rho_carried,
            'rho_offered': rho_offered,
            'A_0': a,
            'p0': p0,
            'L': L,
            'Lq': Lq,
            'W': W,
            'Wq': Wq,
            'p_loss': p_loss,
            'lambda_eff': lambda_eff,
            'p_n': p_n,
            'unstable': False,
            # Slideset aliases (Cerroni notation)
            'A': L,
            'A_c': Lq,
            'A_s': (1.0 - p_loss) * a,
            'A_p': p_loss * a,
            'delta_bar': W,
            'eta_bar': Wq,
            'theta_bar': 1.0 / mu,
            'epsilon_bar': epsilon_bar,
            'pi_p': p_loss,
            'pi_r': pi_r,
            'lambda_s': lambda_eff,
            'lambda_p': lam * p_loss,
        }

    @staticmethod
    def solve_mg1_pollaczek_khinchine(lam: float, service_dist: Distribution) -> dict:
        es = service_dist.mean()
        if es <= 0 or lam <= 0:
            return {}
        a = lam * es
        rho = a
        if rho >= 1.0:
            return {'unstable': True, 'rho': 1.0, 'rho_offered': rho, 'A_0': a}

        es2 = service_dist.second_moment()
        Wq = (lam * es2) / (2.0 * (1.0 - rho))
        W = Wq + es
        Lq = lam * Wq
        L = lam * W

        return {
            'rho': rho,
            'rho_offered': rho,
            'A_0': a,
            'L': L,
            'Lq': Lq,
            'W': W,
            'Wq': Wq,
            'p_loss': 0.0,
            'unstable': False,
            # Slideset aliases (Cerroni notation)
            'A': L,
            'A_c': Lq,
            'A_s': a,
            'A_p': 0.0,
            'delta_bar': W,
            'eta_bar': Wq,
            'theta_bar': es,
            'epsilon_bar': (Wq / rho) if rho > 0 else 0.0,
            'pi_p': 0.0,
            'pi_r': rho,
            'lambda_s': lam,
            'lambda_p': 0.0,
        }