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
        c: int,
        K: float,
        priority: bool,
    ) -> str:
        syms = set(d.kendall_symbol() for d in arrival_dists.values() if d is not None)
        arr_sym = list(syms)[0] if len(syms) == 1 else 'G'
        serv_sym = service_dist.kendall_symbol()
        if math.isinf(K):
            cap_str = 'inf'
        elif priority:
            cap_str = f"{c}+3x{int(K)}"
        else:
            cap_str = str(c + int(K))
        prio_str = " (Priority)" if priority else " (FIFO)"
        return f"{arr_sym}/{serv_sym}/{c}/{cap_str}{prio_str}"

    @staticmethod
    def solve_mmc_infinite(lam: float, mu: float, c: int) -> dict:
        if lam <= 0 or mu <= 0:
            return {}
        a = lam / mu
        rho = a / c
        if rho >= 1.0:
            return {'unstable': True, 'rho': 1.0, 'rho_offered': rho, 'A_0': a}

        sum_terms = sum((a ** n) / math.factorial(n) for n in range(c))
        c_term = (a ** c) / (math.factorial(c) * (1.0 - rho))
        p0 = 1.0 / (sum_terms + c_term)
        p_c = c_term * p0

        Lq = p_c * rho / (1.0 - rho)
        Wq = Lq / lam
        W = Wq + 1.0 / mu
        L = Lq + a

        p_n = {}
        for n in range(c + 20):
            if n <= c:
                p_n[n] = p0 * (a ** n) / math.factorial(n)
            else:
                p_n[n] = p0 * (a ** n) / (math.factorial(c) * (c ** (n - c)))

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
    def solve_mmc_finite(lam: float, mu: float, c: int, K_queue: int) -> dict:
        if lam <= 0 or mu <= 0:
            return {}
        K_sys = c + K_queue
        a = lam / mu
        rho_offered = a / c

        coeffs = []
        for n in range(K_sys + 1):
            if n <= c:
                coeffs.append((a ** n) / math.factorial(n))
            else:
                coeffs.append((a ** n) / (math.factorial(c) * (c ** (n - c))))

        sum_coeffs = sum(coeffs)
        p0 = 1.0 / sum_coeffs
        p_n = {n: p0 * coeffs[n] for n in range(K_sys + 1)}

        p_loss = p_n[K_sys]
        lambda_eff = lam * (1.0 - p_loss)
        rho_carried = lambda_eff / (c * mu)

        L = sum(n * p_n[n] for n in range(K_sys + 1))
        Lq = sum(max(0, n - c) * p_n[n] for n in range(K_sys + 1))
        W = L / lambda_eff if lambda_eff > 0 else 0.0
        Wq = Lq / lambda_eff if lambda_eff > 0 else 0.0

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
            'pi_p': p_loss,
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
            'pi_p': 0.0,
            'lambda_s': lam,
            'lambda_p': 0.0,
        }