from dataclasses import asdict, dataclass


@dataclass
class CoincidenceResults:
    channel1_counts: int
    channel2_counts: int
    coincidences: int
    channel1_rate: float
    channel2_rate: float
    coincidence_rate: float
    accidental_rate: float
    contrast_CAR: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, values):
        return cls(**values)
