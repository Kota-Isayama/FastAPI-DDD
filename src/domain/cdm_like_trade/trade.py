import dataclasses
import datetime
from decimal import Decimal
import enum
from typing import TypeAlias, Union





class Currency(enum.Enum):
    JPY = "jpy"
    USD = "usd"


UnitType = CapacityUnitEnum | WeatherUnitEnum | FinancialUnitEnum | Currency


@dataclasses.dataclass(frozen=True)
class Measure:
    value: Decimal
    unit: UnitType | None


@dataclasses.dataclass(frozen=True)
class DatedValue:
    date: datetime.date
    value: Decimal


@dataclasses.dataclass(frozen=True)
class MeatureSchedule(Measure):
    value: Decimal
    unit: UnitType | None
    dated_values: tuple[DatedValue]


@dataclasses.dataclass(frozen=True)
class PriceSchedule:
    value: Decimal
    unit: UnitType | None
    dated_values: tuple[DatedValue]

    # per_unit_type: UnitType
    # price_type: PriceType
    # price_expression: PriceExpressionEnum
    # composite: PriceComposite
    # arithmetic_operator: ArithmeticOperator
    # cash_price: CashPrice 





@dataclasses.dataclass(frozen=True)
class Address:
    """
    Rune DSLのmetadata addressの簡易版
    例: PriceQuantity.quantity / PriceQuantity.priceを指す
    """
    target_type: str
    attribute_name: str

    def __str__(self):
        return f"{self.target_type}.{self.attribute_name}"
    

@dataclasses.dataclass(frozen=True)
class StepSchedule:
    """
    期間ごとの値を持つ単純なスケジュール。
    例:
        P1 -> 100_000_000
        P2 -> 80_000_000
        P3 -> 60_000_000
    """
    values_by_period: dict[str, float]

    def value_for(self, period: str) -> float:
        if period not in self.values_by_period:
            raise KeyError(f"Period '{period}' not found in schedule.")
        return self.values_by_period[period]


@dataclasses.dataclass(frozen=True)
class PriceQuantity:
    """
    CDM の PriceQuantity をかなり簡略化した理解用モデル。
    quantity と price を一つの箱に持つ。
    """
    quantity: StepSchedule
    price: StepSchedule


@dataclasses.dataclass(frozen=True)
class QuantityScheduleRef:
    """
    quantityScheduleがPriceQuantity.quantityをpointsToするイメージ。
    自身は値を持たず、addressを通じて別オブジェクトから取得する。
    """
    address: Address = dataclasses.field(default_factory=lambda: Address("PriceQuantity", "quantity"))

    def resolve(self, price_quantity: PriceQuantity) -> StepSchedule:
        if self.address.target_type != "PriceQuantity" or self.address.attribute_name != "quantity":
            raise ValueError
        return price_quantity.quantity


@dataclasses.dataclass(frozen=True)
class RateScheduleRef:
    """
    RateSchedule.price が PriceQuantity.price を pointsTo するイメージ。
    """
    def resolve_price_schedule(self, price_quantity: PriceQuantity) -> StepSchedule:
        if self.price_address.target_type != "PriceQuantity" or self.price_address.attribute_name != "price":
            raise ValueError(f"Unsupported address for rate schedule: {self.price_address}")
        return price_quantity.price



class ResolvablePriceQuantity:
    resolved_quantity: Quantity | None
    quantity_schedule: NonNegativeQuantitySchedule | None
    quantity_reference: ResolvablePriceQuantity | None
    quantity_multiplier: QunatityMultiplier | None
    reset: bool | None
    future_value_notional: FutureValueAmount | None
    price_schedule: list[PriceSchedule]


class RateSchedule:
    price: PriceSchedule


class PayoutBase:
    payer_receiver: str
    price_quantity: ResolvablePriceQuantity
    # principal_payment: PrincipalPayment
    # settlement_terms: SettlementTerms


class AssetPayout:
    ...


class CommodityPayout:
    ...

class CreditDefaultPayout:
    ...

class FixedPricePayout:
    ...

class InterestRatePayout(PayoutBase):
    payer_receiver: str
    currency: str
    quantity_schedule: QuantityScheduleRef
    rates_schedule: RateScheduleRef

    rate_schedule: RateSchedule

    calculation_periods: list[str]
    payments_dates: list[datetime.date]
    day_count_fraction: dict[str, float]

class OptionPayout:
    ...

class SettlementPayout:
    ...

"""composableな支払いタイプを定義。
    
    各Payoutは契約当事者間の金銭的義務に関する一連の条件を記述する。
    Payoutを組み合わせる(compose)することで商品を構成する。

    cash取引では、settlement payoutが使われる。
    デリバティブでは、２つの金利payoutを組み合わせることで金利スワップを表現できる。
    一つの金利payoutと1つのクレジットデフォルトpayoutを組み合わせることでクレジットデフォルトスワップを表現できる。
    """
Payout: TypeAlias = AssetPayout | CommodityPayout | CreditDefaultPayout | FixedPricePayout | InterestRatePayout | OptionPayout | SettlementPayout
    


class EconomicTerms:
    """商品に関するすべての要素を表す。
    
    具体的には
    - 支払い構成要素
    - 想定元本/数量
    - 有効日
    - 終了日
    - すべての支払いに適用される日付調整条項
    - 取引可能条項、延長可能条項、早期解約条項、異常自体条項など
    - 取引期間中に当事者間で行われるすべての支払い・送金に関する約束
    """
    effective_date: datetime.date
    termination_date: datetime.date
    date_adjustment: str  # 共通の日付調整
    payouts: tuple[Payout, ...]
    termination_provision: ...  # 早期終了条項があれば
    calculation_agant: ...  # 計算主体があれば
    non_standardized_terms: list[bool]  # 不明
    collateral: Collateral  # 担保  リパ債の時は使用できる？

class TransferableProduct:
    """受け渡し可能な商品"""
    identifer: Identifer
    taxonomy: ...
    economic_terms: EconomicTerms

class NonTransferableProduct:
    """二者間契約と呼ばれ、受け渡しできないもの。スワップなどはこれ。経済効果を柔軟に表現する必要があるため、economicTermsという属性がある。"""
    identifier: ProductIdentifier
    taxonomy: ...  # 商品分類。EconomicTermsから類推されるもので、ものによっては複数種類の値を取ることがある。
    economic_terms: EconomicTerms

Product: TypeAlias = Union[TransferableProduct, NonTransferableProduct]

class TradeLot:
    """価格と数量"""
    price: Price
    quantity: Quantity

class TradableProduct:
    """商品本体 + 売買単位として必要な情報"""
    counterparty: tuple[Counterparty, Counterparty]
    trade_lot: Price | Quantity
    product: Product  # productの数量


class Trade:
    """取引全体の外箱"""
    trade_date: datetime.date
    # execution_details: ...
    # contract_details: ...

    tradable_product: TradableProduct