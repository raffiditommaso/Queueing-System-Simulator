"""
Stochastic distributions providing random variate sampling and analytical moments.
"""

import math
import random
from .constants import to_subscript


class Distribution:
    """Base class for stochastic distributions providing sampling and theoretical moments."""
    def __init__(self, name: str, params: dict):
        self.name = name
        self.params = params

    def sample(self) -> float:
        raise NotImplementedError

    def mean(self) -> float:
        raise NotImplementedError

    def variance(self) -> float:
        raise NotImplementedError

    def second_moment(self) -> float:
        m = self.mean()
        return self.variance() + m * m

    def cv(self) -> float:
        """Coefficient of variation: sigma / mean"""
        m = self.mean()
        return math.sqrt(max(0.0, self.variance())) / m if m > 0 else 0.0

    def kendall_symbol(self) -> str:
        return 'G'

    def summary_str(self) -> str:
        param_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({param_str})"


class ExponentialDist(Distribution):
    def __init__(self, rate: float = 1.0):
        super().__init__('Exponential', {'rate': float(rate)})
        self.rate = max(1e-6, float(rate))

    def sample(self) -> float:
        return random.expovariate(self.rate)

    def mean(self) -> float:
        return 1.0 / self.rate

    def variance(self) -> float:
        return 1.0 / (self.rate * self.rate)

    def kendall_symbol(self) -> str:
        return 'M'


class DeterministicDist(Distribution):
    def __init__(self, value: float = 1.0):
        super().__init__('Deterministic', {'value': float(value)})
        self.val = max(1e-6, float(value))
        self.value = self.val

    def sample(self) -> float:
        return self.val

    def mean(self) -> float:
        return self.val

    def variance(self) -> float:
        return 0.0

    def kendall_symbol(self) -> str:
        return 'D'


class UniformDist(Distribution):
    def __init__(self, a: float = 0.5, b: float = 1.5):
        a_f = float(a)
        b_f = max(a_f + 1e-6, float(b))
        super().__init__('Uniform', {'a': a_f, 'b': b_f})
        self.a = a_f
        self.b = b_f

    def sample(self) -> float:
        return random.uniform(self.a, self.b)

    def mean(self) -> float:
        return (self.a + self.b) / 2.0

    def variance(self) -> float:
        return ((self.b - self.a) ** 2) / 12.0

    def kendall_symbol(self) -> str:
        return 'U'


class ErlangDist(Distribution):
    """Erlang-k distribution: sum of k independent exponential variables."""
    def __init__(self, k: int = 2, mean: float = 1.0):
        k_val = max(1, int(k))
        m_val = max(1e-6, float(mean))
        super().__init__('Erlang', {'k': k_val, 'mean': m_val})
        self.k = k_val
        self.mean_val = m_val
        self.stage_rate = self.k / self.mean_val

    def sample(self) -> float:
        return sum(random.expovariate(self.stage_rate) for _ in range(self.k))

    def mean(self) -> float:
        return self.mean_val

    def variance(self) -> float:
        return (self.mean_val ** 2) / self.k

    def kendall_symbol(self) -> str:
        return f'E{to_subscript(self.k)}'


class HyperexponentialDist(Distribution):
    """2-Phase Hyperexponential: models bursty customer arrivals (Cv > 1)."""
    def __init__(self, p1: float = 0.4, rate1: float = 0.5, rate2: float = 2.0):
        p1 = max(0.01, min(0.99, float(p1)))
        r1 = max(1e-6, float(rate1))
        r2 = max(1e-6, float(rate2))
        super().__init__('Hyperexponential', {'p1': p1, 'rate1': r1, 'rate2': r2})
        self.p1 = p1
        self.r1 = r1
        self.r2 = r2

    def sample(self) -> float:
        if random.random() < self.p1:
            return random.expovariate(self.r1)
        else:
            return random.expovariate(self.r2)

    def mean(self) -> float:
        return (self.p1 / self.r1) + ((1.0 - self.p1) / self.r2)

    def variance(self) -> float:
        ex2 = 2.0 * ((self.p1 / (self.r1 ** 2)) + ((1.0 - self.p1) / (self.r2 ** 2)))
        m = self.mean()
        return max(0.0, ex2 - m * m)

    def kendall_symbol(self) -> str:
        return 'H₂'


class ParetoDist(Distribution):
    """Pareto distribution: Heavy-tailed distribution for bursty Internet traffic."""
    def __init__(self, shape: float = 2.5, scale: float = 0.6):
        alpha = max(1.05, float(shape))
        xm = max(1e-6, float(scale))
        super().__init__('Pareto', {'shape': alpha, 'scale': xm})
        self.alpha = alpha
        self.xm = xm

    def sample(self) -> float:
        u = max(1e-12, random.random())
        return self.xm / (u ** (1.0 / self.alpha))

    def mean(self) -> float:
        if self.alpha > 1:
            return (self.alpha * self.xm) / (self.alpha - 1.0)
        return float('inf')

    def variance(self) -> float:
        if self.alpha > 2:
            return (self.alpha * (self.xm ** 2)) / (((self.alpha - 1.0) ** 2) * (self.alpha - 2.0))
        return float('inf')

    def kendall_symbol(self) -> str:
        return 'Pareto'


def create_distribution(dist_type: str, **kwargs) -> Distribution:
    d = dist_type.lower()
    if 'exp' in d:
        return ExponentialDist(rate=kwargs.get('rate', 1.0))
    elif 'det' in d:
        return DeterministicDist(value=kwargs.get('value', 1.0))
    elif 'uni' in d:
        return UniformDist(a=kwargs.get('a', 0.5), b=kwargs.get('b', 1.5))
    elif 'erl' in d:
        return ErlangDist(k=int(kwargs.get('k', 2)), mean=kwargs.get('mean', 1.0))
    elif 'hyper' in d:
        return HyperexponentialDist(
            p1=kwargs.get('p1', 0.4),
            rate1=kwargs.get('rate1', 0.5),
            rate2=kwargs.get('rate2', 2.0),
        )
    elif 'pareto' in d:
        return ParetoDist(shape=kwargs.get('shape', 2.5), scale=kwargs.get('scale', 0.6))
    else:
        return ExponentialDist(rate=1.0)