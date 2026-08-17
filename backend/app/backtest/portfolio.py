from dataclasses import dataclass, field


@dataclass
class Trade:
    entry_timestamp: object
    entry_price: float
    direction: int
    exit_timestamp: object = None
    exit_price: float = None
    pnl: float = None
    feature_vector: dict = None


@dataclass
class Portfolio:
    initial_cash: float
    cash: float = field(init=False)
    position_direction: int = 0
    entry_price: float = None
    entry_timestamp: object = None
    entry_features: dict = None
    trades: list = field(default_factory=list)

    def __post_init__(self):
        self.cash = self.initial_cash

    def has_open_position(self) -> bool:
        return self.position_direction != 0

    def open_position(self, direction: int, price: float, timestamp, features: dict) -> None:
        self.position_direction = direction
        self.entry_price = price
        self.entry_timestamp = timestamp
        self.entry_features = features

    def close_position(self, price: float, timestamp, fee_rate: float, slippage_rate: float) -> None:
        exit_price = price * (1 - slippage_rate) if self.position_direction == 1 else price * (1 + slippage_rate)
        raw_pnl = (exit_price - self.entry_price) * self.position_direction
        fee = abs(exit_price) * fee_rate
        net_pnl = raw_pnl - fee

        self.trades.append(
            Trade(
                entry_timestamp=self.entry_timestamp,
                entry_price=self.entry_price,
                direction=self.position_direction,
                exit_timestamp=timestamp,
                exit_price=exit_price,
                pnl=net_pnl,
                feature_vector=self.entry_features,
            )
        )

        self.cash += net_pnl
        self.position_direction = 0
        self.entry_price = None
        self.entry_timestamp = None
        self.entry_features = None