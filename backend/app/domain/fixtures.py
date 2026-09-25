from app.domain.models import Property


REAL_PAKISTANI_PROPERTIES = {
    1: {
        "title": "Emaar Coral Towers 2-Bed Oceanfront Luxury Apartment, Crescent Bay, DHA Phase 8, Karachi",
        "developer": "Emaar Pakistan",
        "payment_plan": "Direct transfer with immediate possession, complete sub-lease & original allotment documents",
        "schools": ["Karachi Grammar School (KGS Clifton)", "CAS School DHA Phase 8", "The City School DHA Campus"],
        "hospitals": ["South City Hospital Clifton", "National Medical Centre (NMC) DHA Phase 1", "Aga Khan University Hospital Clifton Clinic"],
        "amenities": ["panoramic sea view balcony", "100% standby generator", "dedicated basement parking", "Otis high-speed passenger elevator", "prayer hall", "Italian marble flooring", "24/7 CCTV surveillance"],
    },
    2: {
        "title": "Dolmen Marine Heights 3-Bed Luxury Sea-Facing Penthouse, Block 2 Clifton, Karachi",
        "developer": "Dolmen Group",
        "payment_plan": "30% down payment on booking, balance in 12 monthly installments, SBP bank financing eligible",
        "schools": ["Karachi Grammar School (KGS)", "Bay View Academy Clifton", "Convent of Jesus and Mary Karachi"],
        "hospitals": ["South City Hospital Clifton", "Dr. Ziauddin Hospital Clifton", "Aga Khan Medical Services Clifton"],
        "amenities": ["central VRF air conditioning", "imported Spanish tile flooring", "24/7 armed security guard patrol", "standby power generator", "covered resident parking", "swimming pool & fitness gym"],
    },
    3: {
        "title": "Precinct 1 Ali Block 350 Sq Yd Luxury Designer Villa, Main Jinnah Avenue, Bahria Town Karachi",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Full payment completed with transfer letter and utility clearance",
        "schools": ["Roots Millennium School Bahria Town", "Beaconhouse Bahria Campus", "Cadet College Karachi"],
        "hospitals": ["Bahria Town International Hospital", "Dr. Ziauddin Hospital Super Highway"],
        "amenities": ["solar net-metering 15kW system", "landscaped private lawn", "designer show kitchen", "servant quarter with attached bath", "community clubhouse & pool"],
    },
    4: {
        "title": "Executive 2-Bed Luxury Furnished Residence, Khayaban-e-Bukhari Commercial, DHA Phase 6, Karachi",
        "developer": "Habib Construction Services",
        "payment_plan": "1-year advance rent with 2 months refundable security deposit via bank pay order",
        "schools": ["Beaconhouse Defence Campus", "The CAS School DHA", "Karachi Grammar Middle School"],
        "hospitals": ["National Medical Centre (NMC)", "South City Hospital Clifton", "Medwin Hospital DHA"],
        "amenities": ["fully furnished with designer interiors", "dedicated covered car parking", "high-speed fiber internet", "24/7 building security", "backup power generator"],
    },
    5: {
        "title": "Ocean View 3-Bed Ultra-Luxury Furnished Penthouse, Marine Promenade, Clifton Block 2, Karachi",
        "developer": "Emaar Pakistan",
        "payment_plan": "Bi-annual advance rental with bank guarantee and diplomatic tenant clearance",
        "schools": ["Bay View Academy Clifton", "Karachi Grammar School", "St. Michael's Convent School"],
        "hospitals": ["South City Hospital Clifton", "Dr. Ziauddin Hospital Clifton", "Aga Khan Clifton Clinic"],
        "amenities": ["unobstructed Arabian Sea views", "private terrace lounge", "smart home automation", "imported hardwood floors", "dual passenger elevators", "24/7 concierge"],
    },
    6: {
        "title": "Midway Commercial Executive Furnished Penthouse, Jinnah Avenue, Bahria Town Karachi",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Quarterly rent payment with corporate lease agreement",
        "schools": ["Roots Millennium School Bahria", "Beaconhouse School System"],
        "hospitals": ["Bahria International Hospital", "Medicare Medical Center"],
        "amenities": ["central air conditioning", "uninterrupted power supply (zero load shedding)", "covered parking", "high-speed elevators"],
    },
    7: {
        "title": "Grade-A Corporate Office Suite, Khayaban-e-Shahbaz Commercial Area, DHA Phase 6, Karachi",
        "developer": "DHA Developments & Cantonment Board",
        "payment_plan": "Cash settlement with verified sub-registrar deed and commercial transfer tax clearance",
        "schools": ["DHA College for Men", "The City School DHA Campus"],
        "hospitals": ["National Medical Centre (NMC)", "South City Hospital Clifton"],
        "amenities": ["open-plan executive workspace", "fiber optic backbone", "dedicated server room with fire suppression", "reserved basement parking slots", "dual backup generators"],
    },
    8: {
        "title": "Dolmen Executive Tower Grade-A Corporate Office Floor, Marine Drive, Clifton Block 4, Karachi",
        "developer": "Dolmen Group",
        "payment_plan": "25% down payment on booking, balance in 24 monthly installments, SBP approved",
        "schools": ["Karachi Grammar School", "Bay View Academy"],
        "hospitals": ["South City Hospital Clifton", "Dr. Ziauddin Hospital Clifton"],
        "amenities": ["turnkey Grade-A office floor", "high-speed destination elevators", "central chilled-water HVAC", "BMS building management system", "multi-level covered parking", "sea-view boardrooms"],
    },
    9: {
        "title": "Broadway Commercial Prime Retail Multi-Level Showroom, Jinnah Commercial Avenue, Bahria Town Karachi",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Complete payment with possession and immediate sub-lease rights",
        "schools": ["Roots Millennium School", "Bahria Golf City Academy"],
        "hospitals": ["Bahria International Hospital", "Ziauddin Hospital"],
        "amenities": ["wide main boulevard frontage", "high footfall commercial zone", "dedicated customer parking", "escalators & goods lifts"],
    },
    10: {
        "title": "Emaar Crescent Bay Waterfront High-Yield Investment Suite, DHA Phase 8, Karachi",
        "developer": "Emaar Pakistan",
        "payment_plan": "30% down payment on allotment, 3-year quarterly construction-linked schedule",
        "schools": ["CAS School DHA Phase 8", "Karachi Grammar School"],
        "hospitals": ["South City Hospital Clifton", "National Medical Centre"],
        "amenities": ["guaranteed 8-10% projected rental yield", "high capital appreciation zone", "gated waterfront community", "private marina access", "resort-style amenities"],
    },
    11: {
        "title": "Hoshang Pearl Ultra-Luxury High-Yield Residence Suite, Clifton Civil Lines, Karachi",
        "developer": "Habib Construction Services",
        "payment_plan": "20% down payment on booking, flexible 36-month installment plan with bank escrow",
        "schools": ["Karachi Grammar School", "Convent of Jesus and Mary"],
        "hospitals": ["South City Hospital Clifton", "Aga Khan University Hospital Clinic"],
        "amenities": ["prime diplomatic heritage zone", "high foreign tenant demand", "LEED-certified green building", "valet parking", "executive business lounge"],
    },
    12: {
        "title": "Theme Park Commercial Broadway Multi-Storey Retail Plaza, Bahria Town Karachi",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "100% upfront payment with guaranteed corporate tenancy agreements",
        "schools": ["Beaconhouse Bahria Campus", "Roots Millennium"],
        "hospitals": ["Bahria International Hospital"],
        "amenities": ["facing world-class theme park", "guaranteed commercial footfall", "24/7 security and maintenance", "high ROI commercial lease"],
    },
    13: {
        "title": "10-Marla Modern Spanish Architectural Designer Villa, Sector C, DHA Phase 5, Lahore",
        "developer": "DHA Developments Lahore",
        "payment_plan": "Direct transfer with immediate possession, clear registry & LDA/DHA verification",
        "schools": ["Lahore Grammar School (LGS Defence)", "Beaconhouse Defence Campus", "The City School DHA Lahore"],
        "hospitals": ["National Hospital & Medical Center DHA Phase 1", "Doctors Hospital Johar Town", "Surgimed Hospital"],
        "amenities": ["imported Spanish porcelain tiles", "designer Ash-wood show kitchen", "solid teak wood doors", "servant quarter with attached bath", "landscaped front lawn", "covered 2-car garage"],
    },
    14: {
        "title": "Goldcrest Mall & Residences Luxury 3-Bed Executive Suite, Main Boulevard, Gulberg III, Lahore",
        "developer": "Al Ghurair Giga",
        "payment_plan": "30% down payment on booking, 24 monthly installments, SBP home loan approved",
        "schools": ["Lahore Grammar School (LGS 55 Main Gulberg)", "Aitchison College Lahore", "Convent of Jesus and Mary Lahore"],
        "hospitals": ["Hameed Latif Hospital Garden Town", "United Christian Hospital (UCH) Gulberg", "Doctors Hospital"],
        "amenities": ["central VRF heating and cooling", "infinity heated swimming pool", "fully equipped fitness center", "underground parking with valet", "direct mall access", "24/7 security"],
    },
    15: {
        "title": "1-Kanal Mediterranean Designer House with Private Pool, Eastern Block, Bahria Orchard Lahore",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Full payment completed with transfer letter and registry deed",
        "schools": ["Beaconhouse Bahria Orchard Campus", "Choueifat International School Lahore"],
        "hospitals": ["Bahria International Hospital Orchard", "Sharif Medical City Hospital"],
        "amenities": ["private heated plunge pool", "solar net-metering 20kW system", "designer Italian kitchen", "home theatre lounge", "spacious 4-car driveway"],
    },
    16: {
        "title": "1-Kanal Fully Furnished Diplomatic Residence, Sector G, DHA Phase 5, Lahore",
        "developer": "DHA Developments Lahore",
        "payment_plan": "1-year advance rent with 2 months refundable security deposit via bank pay order",
        "schools": ["Lahore Grammar School Defence", "Beaconhouse DHA Phase 5", "Army Public School (APS)"],
        "hospitals": ["National Hospital DHA Phase 1", "Defence Medical Center", "Aadil Hospital Defence"],
        "amenities": ["fully furnished with custom imported furniture", "100% solar and generator power backup", "perimeter security sensors", "landscaped terrace garden", "servant accommodation"],
    },
    17: {
        "title": "Pace Woodlands Luxury 3-Bed Furnished Townhouse, Gulberg III / Main Boulevard, Lahore",
        "developer": "Pace Pakistan Ltd",
        "payment_plan": "Semi-annual advance rent with standard corporate lease terms",
        "schools": ["Lahore Grammar School Gulberg", "Aitchison College Lahore", "St. Anthony's High School"],
        "hospitals": ["Hameed Latif Hospital", "Gulberg Hospital & Diagnostic Center", "Surgimed Hospital"],
        "amenities": ["gated residential enclave", "lush green landscaped parks", "community swimming pool and gym", "24/7 armed security", "covered parking"],
    },
    18: {
        "title": "Executive 10-Marla Modern Furnished Villa, Central Block, Bahria Orchard Lahore",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Quarterly rent payment with tenant background verification",
        "schools": ["Beaconhouse Bahria Orchard", "Lahore Grammar School Raiwind Road"],
        "hospitals": ["Bahria International Hospital Orchard", "Sharif Medical City Hospital"],
        "amenities": ["modern contemporary furnishings", "central water filtration", "uninterrupted electricity", "peaceful gated community"],
    },
    19: {
        "title": "Commercial Broadway Grade-A Corporate Office Floor, CCA-1, DHA Phase 5, Lahore",
        "developer": "DHA Developments Lahore",
        "payment_plan": "Cash settlement with verified DHA commercial transfer and stamp duty clearance",
        "schools": ["Lahore Grammar School DHA", "DHA Senior School for Boys"],
        "hospitals": ["National Hospital DHA", "Defence Health Center"],
        "amenities": ["full floor open layout", "high-speed dual elevators", "dedicated multi-car basement parking", "heavy-duty generator power backup", "advanced fire alarms"],
    },
    20: {
        "title": "Al-Hafeez Executive Tower Grade-A Corporate Office Floor, Main Boulevard, Gulberg II, Lahore",
        "developer": "Al-Hafeez Group",
        "payment_plan": "25% booking, 18 equal monthly installments, LDA commercial clearance",
        "schools": ["Lahore Grammar School Gulberg", "Forman Christian College (FC College)"],
        "hospitals": ["Hameed Latif Hospital", "United Christian Hospital Gulberg"],
        "amenities": ["prime Main Boulevard corporate address", "glass curtain wall facade", "central HVAC", "CCTV and biometric access control", "executive boardroom facilities"],
    },
    21: {
        "title": "Central Commercial Broadway Triple-Storey Retail Plaza, Bahria Orchard Lahore",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Full cash purchase with verified possession and immediate rental income",
        "schools": ["Beaconhouse Orchard", "Bahria School System"],
        "hospitals": ["Bahria International Hospital"],
        "amenities": ["triple-storey retail space with basement", "main boulevard commercial visibility", "dedicated customer parking bays", "high rental demand"],
    },
    22: {
        "title": "Zameen Opal High-Rental-Yield 2-Bed Luxury Suite, Land Breeze Housing / DHA, Lahore",
        "developer": "Zameen Developments",
        "payment_plan": "30% down payment on booking, balance in 36 easy monthly installments",
        "schools": ["Lahore Grammar School", "Beaconhouse School System DHA"],
        "hospitals": ["National Hospital DHA", "Doctors Hospital Lahore"],
        "amenities": ["projected 9.5% annual rental yield", "managed rental program available", "rooftop BBQ lounge and garden", "swimming pool", "solar power backup"],
    },
    23: {
        "title": "Tricon Corporate Centre High-Yield Prime Commercial Suite, Main Boulevard Gulberg, Lahore",
        "developer": "Tricon Boston Consulting",
        "payment_plan": "20% down payment, 24 monthly installments, high corporate tenant occupancy",
        "schools": ["Aitchison College", "Lahore Grammar School Gulberg"],
        "hospitals": ["Hameed Latif Hospital", "Doctors Hospital"],
        "amenities": ["AAA-grade corporate investment", "blue-chip corporate tenants in building", "high capital growth corridor", "central air conditioning", "underground parking"],
    },
    24: {
        "title": "Phase 2 Commercial Square Prime Multi-Unit Investment Property, Bahria Orchard Lahore",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "100% paid-up with immediate commercial lease transfer",
        "schools": ["Beaconhouse Orchard", "Choueifat School"],
        "hospitals": ["Bahria International Hospital Orchard"],
        "amenities": ["pre-leased commercial units", "stable monthly rental returns", "zero load shedding", "dedicated security staff"],
    },
    25: {
        "title": "1-Kanal Contemporary Designer Luxury Villa, Sector B, DHA Phase 2, Islamabad",
        "developer": "DHA Islamabad-Rawalpindi",
        "payment_plan": "Direct transfer with immediate possession, clean title & DHA Islamabad verification",
        "schools": ["Roots Millennium School DHA-2 Campus", "Army Public School (APS) DHA-2", "Froebel's International School"],
        "hospitals": ["DHA Medical Center Phase 2", "Al-Shifa Eye Hospital", "Riphah International Hospital"],
        "amenities": ["imported Grohe and Kohler bathroom fittings", "solid Ash-wood designer kitchen", "smart home automation", "spacious 3-car porch", "servant quarters with washroom", "landscaped terrace"],
    },
    26: {
        "title": "Silver Oaks Luxury 3-Bed Executive Penthouse, Sector F-10/4, Margalla Road, Islamabad",
        "developer": "Silver Oaks Developers",
        "payment_plan": "30% down payment on booking, balance in 12 monthly installments, CDA approved",
        "schools": ["Froebel's International School F-7", "Roots Millennium One World Campus F-8", "Head Start School F-10"],
        "hospitals": ["Maroof International Hospital F-10", "Shifa International Hospital H-8", "Kulsum International Hospital Blue Area"],
        "amenities": ["spectacular panoramic Margalla Hills views", "central climate control", "dedicated basement parking", "residents-only clubhouse and fitness center", "24/7 security and concierge"],
    },
    27: {
        "title": "Sector A Margalla Hills View 1-Kanal Designer Villa, Bahria Enclave, Islamabad",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Complete payment with transfer letter, NOC and utility connection certificates",
        "schools": ["Beaconhouse School System Bahria Enclave", "Head Start School Enclave"],
        "hospitals": ["Bahria Enclave Hospital", "Shifa Medical Center"],
        "amenities": ["breathtaking mountain view", "modern architecture with double-height lobby", "Italian tiled flooring", "solar net-metering installed", "landscaped front & back lawns"],
    },
    28: {
        "title": "Executive 1-Kanal Fully Furnished Diplomatic Villa, Sector E, DHA Phase 2, Islamabad",
        "developer": "DHA Islamabad-Rawalpindi",
        "payment_plan": "1-year advance rent with 2 months refundable security deposit via bank pay order",
        "schools": ["Roots Millennium DHA-2", "Army Public School DHA-2", "Froebel's International"],
        "hospitals": ["DHA Medical Center Phase 2", "Riphah Hospital Islamabad"],
        "amenities": ["complete imported diplomatic furnishings", "perimeter surveillance and guard room", "heavy duty backup generator", "modern American kitchen", "servant quarters"],
    },
    29: {
        "title": "The Centaurus Residences Luxury 3-Bed Diplomatic Suite, Jinnah Avenue, Blue Area / F-8, Islamabad",
        "developer": "Pak Gulf Construction (The Centaurus Group)",
        "payment_plan": "Quarterly or semi-annual advance rent with corporate lease contract",
        "schools": ["Froebel's International School F-7", "Beaconhouse Margalla Campus H-8", "Islamabad Model College"],
        "hospitals": ["Kulsum International Hospital Blue Area", "Shifa International Hospital", "PIMS Hospital Islamabad"],
        "amenities": ["direct private elevator access to Centaurus Mall", "signature five-star spa and rooftop pool", "valet parking", "24/7 armed security", "Margalla Hills facing balcony"],
    },
    30: {
        "title": "Executive 10-Marla Furnished Hillside House, Sector B, Bahria Enclave, Islamabad",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Semi-annual advance rent with standard tenant verification",
        "schools": ["Beaconhouse Bahria Enclave", "Roots Millennium"],
        "hospitals": ["Bahria Enclave Medical Centre", "Shifa Clinic"],
        "amenities": ["fully furnished with modern appliances", "scenic hillside location", "uninterrupted water and gas supply", "gated community security"],
    },
    31: {
        "title": "World Trade Center Islamabad Grade-A Corporate Office Suite, DHA Phase 2, Islamabad",
        "developer": "Al Ghurair Giga",
        "payment_plan": "Cash settlement with verified Giga Mall / WTC management transfer documents",
        "schools": ["Roots Millennium DHA-2", "Army Public School DHA-2"],
        "hospitals": ["DHA Medical Center Phase 2", "Riphah Hospital"],
        "amenities": ["prestigious World Trade Center global branding", "high-speed elevators", "high-capacity telecom backbone", "multi-level covered parking", "attached business hotel"],
    },
    32: {
        "title": "ISE Towers (Islamabad Stock Exchange) Corporate Office Floor, Jinnah Avenue, Blue Area, Islamabad",
        "developer": "Islamabad Stock Exchange Towers Ltd",
        "payment_plan": "25% down payment, 18 monthly installments, prime Blue Area title deed",
        "schools": ["Froebel's International School", "Roots Millennium School F-8"],
        "hospitals": ["Kulsum International Hospital Blue Area", "Shifa International Hospital"],
        "amenities": ["financial district epicenter location", "earthquake-resistant Zone 4 engineering", "intelligent building management system (BMS)", "24/7 security with walkthrough gates", "covered basement parking"],
    },
    33: {
        "title": "Civic Zone Multi-Storey Commercial Broadway Plaza, Bahria Enclave, Islamabad",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "Full cash settlement with registered sale deed and immediate possession",
        "schools": ["Beaconhouse Bahria Enclave", "Head Start Enclave"],
        "hospitals": ["Bahria Enclave Hospital"],
        "amenities": ["front boulevard exposure", "ideal for corporate branches and retail banking", "dedicated customer parking bays", "high commercial rental demand"],
    },
    34: {
        "title": "Giga Mall D-Ground Commercial Investment Retail Showroom, DHA Phase 2, Islamabad",
        "developer": "Al Ghurair Giga",
        "payment_plan": "30% down payment on allotment, 24-month quarterly construction schedule",
        "schools": ["Roots Millennium DHA-2", "Army Public School DHA-2"],
        "hospitals": ["DHA Medical Center", "Al-Shifa Hospital"],
        "amenities": ["exceptional footfall inside premier shopping destination", "pre-leased commercial return potential", "capital appreciation hotspot", "central air conditioning"],
    },
    35: {
        "title": "Elysium Tower High-Rise Luxury Commercial & Residential Investment Suite, Blue Area, Islamabad",
        "developer": "Imarat Group of Companies",
        "payment_plan": "25% down payment on booking, 36 monthly installments, CDA approved",
        "schools": ["Froebel's International School", "Beaconhouse Margalla Campus"],
        "hospitals": ["Kulsum International Hospital Blue Area", "PIMS Hospital"],
        "amenities": ["located directly opposite Centaurus Mall", "high expected rental yield from multinational and diplomatic tenants", "modern architectural facade", "smart building management"],
    },
    36: {
        "title": "Urban Boulevard Commercial High-Rise Investment Project, Bahria Enclave, Islamabad",
        "developer": "Bahria Town (Pvt) Ltd",
        "payment_plan": "100% upfront settlement with high-yield commercial leasing contracts",
        "schools": ["Beaconhouse Bahria Enclave", "Head Start School"],
        "hospitals": ["Bahria Enclave Medical Center"],
        "amenities": ["strategic high-density commercial corner", "multi-tenant rental income", "guaranteed utilities and maintenance", "ample parking"],
    },
}


def demo_properties() -> list[Property]:
    cities = [
        ("Karachi", ["DHA Phase 6", "Clifton", "Bahria Town"]),
        ("Lahore", ["DHA Phase 5", "Gulberg", "Bahria Orchard"]),
        ("Islamabad", ["DHA Phase 2", "F-11", "Bahria Enclave"]),
    ]
    purposes = ["sale", "rent", "commercial", "investment"]
    items: list[Property] = []
    for city_index, (city, areas) in enumerate(cities):
        for purpose_index, purpose in enumerate(purposes):
            for variant in range(3):
                number = len(items) + 1
                available = variant != 2
                price = (18 + city_index * 6 + purpose_index * 8 + variant * 3) * 1_000_000
                prop_info = REAL_PAKISTANI_PROPERTIES.get(number, {})
                amenities = list(prop_info.get("amenities", ["parking", "security", "masjid"]))
                for standard_amenity in ("parking", "security", "masjid"):
                    if not any(standard_amenity in a.lower() for a in amenities):
                        amenities.append(standard_amenity)
                items.append(
                    Property(
                        id=f"PROP-{number:03d}",
                        title=prop_info.get("title", f"{purpose.title()} in {areas[variant]}, {city}"),
                        city=city,
                        area=areas[variant],
                        purpose=purpose,
                        price_pkr=price,
                        bedrooms=0 if purpose == "commercial" else 2 + variant,
                        size_sqft=900 + variant * 450,
                        amenities=amenities,
                        investment_goals=(
                            ["rental yield", "capital appreciation"]
                            if purpose == "investment"
                            else ["capital appreciation"]
                        ),
                        nearby_schools=prop_info.get("schools", [f"{city} Grammar School"]),
                        nearby_hospitals=prop_info.get("hospitals", [f"{city} International Hospital"]),
                        developer=prop_info.get("developer", "Pakistan Real Estate Holdings"),
                        payment_plan=prop_info.get("payment_plan", "Standard flexible installments with bank financing option"),
                        available=available,
                        assigned_employee=["Ayesha Khan", "Hamza Ali", "Sara Ahmed"][variant],
                        source_version="v1.0",
                        source="verified-crm-inventory",
                    )
                )
    return items
