from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FedDomain:
    code: str
    name_zh: str
    name_en: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class FedTopic:
    code: str
    parent_code: str
    name_zh: str
    name_en: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class TaxonomyAssignment:
    primary_topic: str
    cross_tags: tuple[str, ...] = ()


FED_DOMAINS = (
    FedDomain("rates-policy", "货币政策与利率", "Monetary Policy and Rates", 10),
    FedDomain("inflation", "通胀与通胀预期", "Inflation and Expectations", 20),
    FedDomain("growth", "实体经济与增长", "Real Economy and Growth", 30),
    FedDomain("employment", "劳动力市场", "Labor Market", 40),
    FedDomain("credit-banking", "信贷与银行体系", "Credit and Banking", 50),
    FedDomain(
        "financial-markets",
        "金融条件与金融市场",
        "Financial Conditions and Markets",
        60,
    ),
    FedDomain("housing-household", "住房与家庭部门", "Housing and Households", 70),
)

FED_DOMAIN_BY_CODE = {domain.code: domain for domain in FED_DOMAINS}

FED_TOPICS = (
    FedTopic("tv-fed-policy-rates", "rates-policy", "政策利率", "Policy Rates", 10),
    FedTopic(
        "tv-fed-policy-operations",
        "rates-policy",
        "公开市场操作与政策执行",
        "Open Market Operations and Implementation",
        20,
    ),
    FedTopic(
        "tv-fed-central-bank-balance-sheet",
        "rates-policy",
        "央行资产负债表",
        "Central Bank Balance Sheet",
        30,
    ),
    FedTopic(
        "tv-fed-money-supply",
        "rates-policy",
        "货币供应与系统流动性",
        "Money Supply and Liquidity",
        40,
    ),
    FedTopic(
        "tv-fed-rate-transmission",
        "rates-policy",
        "利率传导",
        "Rate Transmission",
        50,
    ),
    FedTopic(
        "tv-fed-headline-inflation",
        "inflation",
        "总体消费通胀",
        "Headline Consumer Inflation",
        10,
    ),
    FedTopic(
        "tv-fed-core-inflation",
        "inflation",
        "核心与趋势通胀",
        "Core and Trend Inflation",
        20,
    ),
    FedTopic("tv-fed-inflation-pce", "inflation", "PCE 通胀", "PCE Inflation", 30),
    FedTopic(
        "tv-fed-inflation-components",
        "inflation",
        "商品与服务通胀",
        "Goods and Services Inflation",
        40,
    ),
    FedTopic(
        "tv-fed-inflation-housing",
        "inflation",
        "住房通胀",
        "Housing Inflation",
        50,
    ),
    FedTopic(
        "tv-fed-inflation-pipeline",
        "inflation",
        "上游价格压力",
        "Pipeline Price Pressures",
        60,
    ),
    FedTopic(
        "tv-fed-wage-pressures",
        "inflation",
        "工资成本压力",
        "Wage Cost Pressures",
        70,
    ),
    FedTopic(
        "tv-fed-inflation-expectations",
        "inflation",
        "通胀预期",
        "Inflation Expectations",
        80,
    ),
    FedTopic("tv-fed-growth-gdp", "growth", "GDP 与国民账户", "GDP and National Accounts", 10),
    FedTopic("tv-fed-consumption-demand", "growth", "消费需求", "Consumption Demand", 20),
    FedTopic("tv-fed-business-investment", "growth", "企业投资", "Business Investment", 30),
    FedTopic("tv-fed-production-capacity", "growth", "生产与产能", "Production and Capacity", 40),
    FedTopic(
        "tv-fed-orders-inventories-sales",
        "growth",
        "订单、库存与销售",
        "Orders, Inventories and Sales",
        50,
    ),
    FedTopic("tv-fed-business-sentiment", "growth", "企业景气", "Business Sentiment", 60),
    FedTopic("tv-fed-fiscal-government", "growth", "财政与政府部门", "Fiscal and Government", 70),
    FedTopic(
        "tv-fed-external-demand", "growth", "对外贸易与外部需求", "Trade and External Demand", 80
    ),
    FedTopic(
        "tv-fed-productivity-potential",
        "growth",
        "生产率与潜在增长",
        "Productivity and Potential Growth",
        90,
    ),
    FedTopic(
        "tv-fed-energy-climate",
        "growth",
        "能源与气候供给约束",
        "Energy and Climate Supply Constraints",
        100,
    ),
    FedTopic("tv-fed-labor-employment", "employment", "就业规模", "Employment", 10),
    FedTopic("tv-fed-labor-demand", "employment", "劳动力需求", "Labor Demand", 20),
    FedTopic(
        "tv-fed-labor-separations",
        "employment",
        "离职、裁员与失业救济",
        "Separations, Layoffs and Claims",
        30,
    ),
    FedTopic("tv-fed-labor-supply", "employment", "劳动力供给", "Labor Supply", 40),
    FedTopic(
        "tv-fed-labor-unemployment",
        "employment",
        "失业与闲置程度",
        "Unemployment and Slack",
        50,
    ),
    FedTopic("tv-fed-labor-wages", "employment", "工资与薪酬", "Wages and Compensation", 60),
    FedTopic(
        "tv-fed-labor-hours",
        "employment",
        "工时、成本与生产率",
        "Hours, Costs and Productivity",
        70,
    ),
    FedTopic(
        "tv-fed-bank-balance-sheet",
        "credit-banking",
        "银行资产负债表",
        "Bank Balance Sheets",
        10,
    ),
    FedTopic("tv-fed-business-credit", "credit-banking", "企业信贷", "Business Credit", 20),
    FedTopic("tv-fed-consumer-credit", "credit-banking", "消费信贷", "Consumer Credit", 30),
    FedTopic("tv-fed-housing-credit", "credit-banking", "住房信贷", "Housing Credit", 40),
    FedTopic(
        "tv-fed-credit-pricing-standards",
        "credit-banking",
        "信贷价格与标准",
        "Credit Pricing and Standards",
        50,
    ),
    FedTopic("tv-fed-credit-quality", "credit-banking", "信用质量", "Credit Quality", 60),
    FedTopic(
        "tv-fed-leverage-debt",
        "credit-banking",
        "杠杆与债务负担",
        "Leverage and Debt Burden",
        70,
    ),
    FedTopic(
        "tv-fed-riskfree-yield-curve",
        "financial-markets",
        "无风险利率与收益率曲线",
        "Risk-Free Rates and Yield Curve",
        10,
    ),
    FedTopic(
        "tv-fed-credit-spreads",
        "financial-markets",
        "信用利差与融资条件",
        "Credit Spreads and Financing Conditions",
        20,
    ),
    FedTopic("tv-fed-fx-dollar", "financial-markets", "美元与外汇", "Dollar and FX", 30),
    FedTopic("tv-fed-capital-flows", "financial-markets", "资本流动", "Capital Flows", 40),
    FedTopic(
        "tv-fed-reserves-external-finance",
        "financial-markets",
        "国际储备与外部融资",
        "International Reserves and External Finance",
        50,
    ),
    FedTopic(
        "tv-fed-equity-volatility-risk",
        "financial-markets",
        "权益、波动与风险偏好",
        "Equity, Volatility and Risk Appetite",
        60,
    ),
    FedTopic(
        "tv-fed-commodity-energy-markets",
        "financial-markets",
        "大宗商品与能源市场",
        "Commodity and Energy Markets",
        70,
    ),
    FedTopic("tv-fed-housing-supply", "housing-household", "住房供给与建设", "Housing Supply", 10),
    FedTopic(
        "tv-fed-housing-transactions", "housing-household", "房屋交易", "Housing Transactions", 20
    ),
    FedTopic(
        "tv-fed-housing-prices",
        "housing-household",
        "房价与可负担性",
        "House Prices and Affordability",
        30,
    ),
    FedTopic("tv-fed-mortgage-market", "housing-household", "按揭市场", "Mortgage Market", 40),
    FedTopic(
        "tv-fed-housing-rents", "housing-household", "租金与居住成本", "Rents and Housing Costs", 50
    ),
    FedTopic("tv-fed-household-income", "housing-household", "家庭收入", "Household Income", 60),
    FedTopic(
        "tv-fed-household-consumption",
        "housing-household",
        "家庭消费与储蓄",
        "Household Consumption and Saving",
        70,
    ),
    FedTopic(
        "tv-fed-household-confidence",
        "housing-household",
        "家庭信心与预期",
        "Household Confidence and Expectations",
        80,
    ),
    FedTopic(
        "tv-fed-household-health",
        "housing-household",
        "人口、健康与家庭福利",
        "Population, Health and Welfare",
        90,
    ),
)

FED_TOPIC_BY_CODE = {topic.code: topic for topic in FED_TOPICS}


def _contains(text: str, *tokens: str) -> bool:
    return any(token in text for token in tokens)


def _assignment(topic: str, *cross_tags: str) -> TaxonomyAssignment:
    return TaxonomyAssignment(topic, tuple(dict.fromkeys(cross_tags)))


def classify_tradingview_indicator(
    *,
    ticker: str,
    name: str,
    route: str | None,
    source_categories: tuple[str, ...],
) -> TaxonomyAssignment:
    text = " ".join((ticker, name, route or "")).casefold().replace("-", " ")
    category = source_categories[0]

    # The shared TradingView catalog occasionally places indicators in a source
    # category that does not match their economic meaning. These semantic rules
    # intentionally run before category-specific fallbacks.
    if "central bank balance sheet" in text:
        return _assignment("tv-fed-central-bank-balance-sheet")
    if _contains(text, "banks balance sheet", "bank balance sheet"):
        return _assignment("tv-fed-bank-balance-sheet")
    if "central bank lending rate" in text:
        return _assignment("tv-fed-policy-rates")
    if "interest rate on new mortgage" in text:
        return _assignment("tv-fed-mortgage-market", "financial-markets")
    if _contains(text, "cash reserve ratio", "refinancing operation"):
        return _assignment("tv-fed-policy-operations")
    if "purchases of government bonds" in text:
        return _assignment("tv-fed-policy-operations", "financial-markets")
    if "debt balance mortgage" in text:
        return _assignment("tv-fed-housing-credit", "housing-household")
    if _contains(text, "debt balance credit card", "debt balance auto", "debt balance student"):
        return _assignment("tv-fed-consumer-credit", "housing-household")
    if "debt balance total" in text:
        return _assignment("tv-fed-leverage-debt", "housing-household")
    if _contains(text, "bank lending rate", "loan prime rate"):
        return _assignment("tv-fed-credit-pricing-standards", "financial-markets")
    if "housing credit" in text:
        return _assignment("tv-fed-housing-credit", "housing-household")
    if _contains(text, "corelogic dwelling", "dwelling price"):
        return _assignment("tv-fed-housing-prices", "inflation")
    if "fixed asset investment" in text:
        return _assignment("tv-fed-business-investment")
    if "energy prices" in text:
        return _assignment("tv-fed-inflation-pipeline", "growth")
    if _contains(text, "business conditions index", "business climate indicator"):
        return _assignment("tv-fed-business-sentiment")
    if _contains(text, "private debt to gdp", "household debt to"):
        return _assignment("tv-fed-leverage-debt", "housing-household")

    if category == "lbr":
        if _contains(text, "claim", "layoff", "discharge", "job cut", "quit"):
            return _assignment("tv-fed-labor-separations")
        if _contains(
            text,
            "job offer",
            "vacan",
            "hiring",
            "job advertisement",
            "applications ratio",
        ):
            return _assignment("tv-fed-labor-demand")
        if _contains(
            text,
            "participation",
            "labor force",
            "labour force",
            "inactivity",
            "retirement",
            "population",
        ):
            return _assignment("tv-fed-labor-supply")
        if _contains(
            text,
            "unemployment",
            "unemployed",
            "employment rate",
            "underemployment",
            "jobless rate",
        ):
            return _assignment("tv-fed-labor-unemployment")
        if _contains(text, "wage", "earning", "employment cost", "benefit", "minimum"):
            return _assignment("tv-fed-labor-wages", "inflation")
        if _contains(text, "hours", "productivity", "labour cost", "labor cost", "unit labor"):
            return _assignment("tv-fed-labor-hours", "growth")
        return _assignment("tv-fed-labor-employment")

    if category == "prce":
        if _contains(text, "expectation", "price trend"):
            return _assignment("tv-fed-inflation-expectations")
        if "pce" in text:
            return _assignment("tv-fed-inflation-pce")
        if _contains(text, "housing", "shelter", "rent"):
            return _assignment("tv-fed-inflation-housing", "housing-household")
        if _contains(
            text,
            "producer",
            "ppi",
            "import price",
            "export price",
            "commodity",
            "food price",
            "energy price",
            "wpi",
        ):
            return _assignment("tv-fed-inflation-pipeline", "growth")
        if _contains(text, "core", "median", "trimmed mean"):
            return _assignment("tv-fed-core-inflation")
        if _contains(text, "goods", "services", "durable", "transport", "medical"):
            return _assignment("tv-fed-inflation-components")
        return _assignment("tv-fed-headline-inflation")

    if category == "gdp":
        if _contains(text, "per capita", "productivity", "potential"):
            return _assignment("tv-fed-productivity-potential")
        return _assignment("tv-fed-growth-gdp")

    if category == "mny":
        if _contains(text, "banks balance sheet", "bank balance sheet"):
            return _assignment("tv-fed-bank-balance-sheet")
        if _contains(text, "loan", "private sector"):
            return _assignment("tv-fed-business-credit")
        if _contains(text, "money supply", " m0", " m1", " m2", " m3", " m4"):
            return _assignment("tv-fed-money-supply")
        if _contains(text, "central bank balance", "central bank asset", "capital account"):
            return _assignment("tv-fed-central-bank-balance-sheet")
        if _contains(
            text, "reverse repo", "repo rate", "liquidity injection", "liquidity withdrawal"
        ):
            return _assignment("tv-fed-policy-operations")
        if _contains(
            text, "federal funds", "interest rate", "deposit rate", "central bank lending"
        ):
            return _assignment("tv-fed-policy-rates")
        if _contains(text, "foreign bond", "foreign stock", "foreign securities"):
            return _assignment("tv-fed-capital-flows", "growth")
        if _contains(text, "foreign exchange reserve", "gold reserve"):
            return _assignment("tv-fed-reserves-external-finance")
        return _assignment("tv-fed-rate-transmission")

    if category == "trd":
        if _contains(text, "reserve", "gold"):
            return _assignment("tv-fed-reserves-external-finance")
        if _contains(text, "capital flow", "direct investment", "foreign investment", "securities"):
            return _assignment("tv-fed-capital-flows", "growth")
        if "external debt" in text:
            return _assignment("tv-fed-leverage-debt", "financial-markets")
        if _contains(text, "crude oil production", "natural gas production"):
            return _assignment("tv-fed-energy-climate")
        return _assignment("tv-fed-external-demand", "financial-markets")

    if category in {"gov", "txs"}:
        if "asylum" in text:
            return _assignment("tv-fed-household-health")
        return _assignment("tv-fed-fiscal-government", "financial-markets")

    if category == "bsnss":
        if "bankrupt" in text:
            return _assignment("tv-fed-credit-quality", "growth")
        if _contains(
            text, "crude", "gasoline", "distillate", "heating oil", "natural gas", "grain stocks"
        ):
            return _assignment("tv-fed-commodity-energy-markets", "inflation", "growth")
        if _contains(text, "productivity", "potential"):
            return _assignment("tv-fed-productivity-potential")
        if _contains(text, "construction", "capital expenditure", "business investment"):
            return _assignment("tv-fed-business-investment")
        if _contains(text, "order", "inventor", "sales", "wholesale", "retail"):
            return _assignment("tv-fed-orders-inventories-sales")
        if _contains(text, "production", "capacity", "output", "car registration"):
            return _assignment("tv-fed-production-capacity")
        return _assignment("tv-fed-business-sentiment")

    if category == "cnsm":
        if _contains(text, "consumer credit", "credit card", "credit account"):
            return _assignment("tv-fed-consumer-credit", "housing-household")
        if _contains(text, "household debt", "debt to income", "debt to gdp"):
            return _assignment("tv-fed-leverage-debt", "housing-household")
        if _contains(text, "confidence", "sentiment", "expectation", "optimism"):
            return _assignment("tv-fed-household-confidence", "growth")
        if _contains(text, "income", "wage"):
            return _assignment("tv-fed-household-income")
        if _contains(text, "gasoline price", "food price"):
            return _assignment("tv-fed-inflation-pipeline", "housing-household")
        return _assignment("tv-fed-household-consumption", "growth")

    if category == "hse":
        if _contains(text, "debt balance mortgage", "housing credit"):
            return _assignment("tv-fed-housing-credit", "housing-household")
        if _contains(text, "mortgage rate", "mortgage size", "mortgage application"):
            return _assignment("tv-fed-mortgage-market", "financial-markets")
        if _contains(text, "price", "affordability", "house value"):
            return _assignment("tv-fed-housing-prices", "inflation")
        if _contains(text, "sale", "transaction"):
            return _assignment("tv-fed-housing-transactions", "growth")
        if _contains(text, "rent", "shelter"):
            return _assignment("tv-fed-housing-rents", "inflation")
        return _assignment("tv-fed-housing-supply", "growth")

    if category == "hlth":
        return _assignment("tv-fed-household-health")
    if category in {"enrg", "clmt"}:
        return _assignment("tv-fed-energy-climate")

    raise ValueError(f"Unsupported TradingView source category: {category}")
