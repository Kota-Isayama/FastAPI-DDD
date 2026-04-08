import dataclasses


@dataclasses.dataclass(frozen=True)
class FxOptionBundleTerms:
    customer_name: str
    currency_pair: str
    
    import_or_export: str 

    schedule_terms: FxOptionBundleScheduleTerms
    lesg: list["FxOptionLegDraftTerms"]
    bundle_barrier_terms: "FxOptionBundleBarrierTerms"
    premium_terms: "FxOptionBundlePremiumTerms"
    