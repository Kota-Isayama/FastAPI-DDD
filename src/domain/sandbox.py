import datetime
from decimal import Decimal

from domain.contract_model import BusinessDayConvention, ContractForm, CouponLeg, Currency, DateRole, FixedRateFormula, FormulaBinding, OffsetUnit, PartyRef, PartyRoleAssignment, PatternScheduleSource, ReferenceRef, RelativeDateSchedule, RelativeDateScheduleSource, ScheduleMeaning, ScheduleNode, ScheduleNodeId, ScheduleOwner, ScheduleOwnerType, SchedulePattern, ScheduleRef, ScheduleSource, SteppedDecimal, UnderlierRef


if __name__ == "__main__":
    # 1-1
    payment_meaning = ScheduleMeaning(
        roles=frozenset(DateRole.PAYMENT),
        owner=ScheduleOwner(owner_type=ScheduleOwnerType.LEG, owner_id="sample_coupon"),
    )

    fixing_meaning = ScheduleMeaning(
        roles=frozenset(DateRole.FIXING),
        owner=ScheduleOwner(owner_type=ScheduleOwnerType.LEG, owner_id="sample_coupon")
    )

    # 1-2

    payment_date_node_id = ScheduleNodeId(value="sample_node")
    payment_dates_source = PatternScheduleSource(
        pattern=SchedulePattern(
            start_date=datetime.date(2026, 4, 23),
            end_date=datetime.date(2027, 4, 23),
            frequency="QUARTERLY",
            business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
        )
    )
    payment_dates_node = ScheduleNode(
        node_id=payment_date_node_id,
        meaning=payment_meaning,
        source=payment_dates_source,
    )

    fixing_node_id = ScheduleNodeId(value="sample_node2")
    fixing_node_source = RelativeDateScheduleSource(
        base_ref=ScheduleRef(node_id="sample_node"),
        relation=RelativeDateSchedule(offset=-2, unit=OffsetUnit.BUSINESS_DAYS)
    )
    fixing_node = ScheduleNode(
        node_id=fixing_node_id,
        meaning=fixing_meaning,
        source=fixing_node_source,
    )

    # 1-4
    usdjpy = ReferenceRef(symbol="USDJPY", kind="FX")
    payment_and_fixing_node_id = ScheduleNodeId(value="sample_fixing_and_payment")
    payment_and_fixing_node = ScheduleNode(
        node_id=payment_and_fixing_node_id,
        meaning=ScheduleMeaning(roles=(DateRole.FIXING, DateRole.PAYMENT), owner=ScheduleOwner(owner_type=ScheduleOwnerType.LEG, owner_id="owner_id")),
        source=PatternScheduleSource(
            pattern=SchedulePattern(
                start_date=datetime.date(2026, 4, 23),
                end_date=datetime.date(2026, 4, 23),
                frequency="SEMI_ANNUAL"
            )
        ),
    )

    # 2-1
    contract_form = ContractForm(
        form_id="form_id",
        form_kind="form_kind",
        parties=(PartyRef(party_id="party1", display_name="party1"), PartyRef(party_id="party2", display_name="party2")),
        party_roles=(PartyRoleAssignment(role="party1", party_id="party1"), PartyRoleAssignment(role="party2", party_id="party2")),
        references=(usdjpy,),
        transfers=(),
        legs=(),
        formulas=(),
        mechanisms=(),
        overrides=(),
        schedule_patches=(),
        schedule_nodes=(payment_dates_node, fixing_node),
        schedule_node_patches=(),
        tags={},
    )


    # 2-2
    coupon_leg = CouponLeg(
        component_id="coupon_leg",
        payer_party_id="party1",
        receiver_party_id="party2",
        reference=underlier,
        notional=SteppedDecimal(initial=Decimal("1000000")),
        payment_schedule=ScheduleRef(node_id=payment_date_node_id),
        rate_formula_name="formula",
        currency=Currency.JPY,
    )
    contract_form = ContractForm(
        form_id="form_id",
        form_kind="form_kind",
        parties=(PartyRef(party_id="party1", display_name="party1"), PartyRef(party_id="party2", display_name="party2")),
        party_roles=(PartyRoleAssignment(role="party1", party_id="party1"), PartyRoleAssignment(role="party2", party_id="party2")),
        references=(underlier,),
        transfers=(),
        legs=(coupon_leg,),
        formulas=(
            FormulaBinding(name="formula", formula=FixedRateFormula(SteppedDecimal("0.08"))),
        ),
        mechanisms=(),
        overrides=(),
        schedule_patches=(),
        schedule_nodes=(payment_dates_node, fixing_node),
        schedule_node_patches=(),
        tags={},
    )

    
    # 2-3
    materialized = contract_form.materialize()
    # print(materialized.schedule_nodes)
    print(materialized.resolve_schedule_ref(ScheduleRef(node_id=payment_date_node_id)))


    # 3-1
    usdjpy = ReferenceRef("USDJPY", kind="FX")
    coupon_payment = ScheduleNode(
        node_id=ScheduleNodeId("3-1-payment"),
        meaning=ScheduleMeaning(roles=(DateRole.PAYMENT,), owner=ScheduleOwner(owner_type=ScheduleOwnerType.LEG, owner_id="owner_id??")),
        source=SchedulePattern(start_date=datetime.date(2026, 4, 21), end_date=datetime.date(2027, 4, 21), frequency="QUARTERLY"),
    )
    coupon_fixing = ScheduleNode(
        node_id=ScheduleNodeId("3-1-fixing"),
        meaning=ScheduleMeaning(roles=(DateRole.FIXING,), owner=ScheduleOwner(owner_type=ScheduleOwnerType.LEG, owner_id="owner_id??")),
        source=RelativeDateScheduleSource(
            base_ref=coupon_payment.node_id,
            relation=RelativeDateSchedule(offset=-2),
        ),
    )
    base_currency_coupon_leg = CouponLeg(
        component_id="coupon_leg",
        payer_party_id="party1",
        receiver_party_id="party2",
        reference=usdjpy,
        notional=SteppedDecimal(Decimal("10000")),
        payment_schedule=coupon_payment,
        rate_formula_name="???",
        currency=Currency.USD,
    )
    
    
    coupon_swap_contract = ContractForm(
        form_id="coupon_swap",
        form_kind="coupon_swap",
        parties=(PartyRef("party1", "party1"), PartyRef("party2", "party2")),
        party_roles=(PartyRoleAssignment(role="base_currency_payer", party_id="party1"), PartyRoleAssignment(role="quote_currency_payer", party_id="party2")),
        references=(usdjpy, ),
        transfers=(),
        legs=()
    )