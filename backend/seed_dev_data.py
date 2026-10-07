"""Seed rich verified properties in Islamabad & Rawalpindi for local development."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models import Property
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import SessionLocal
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AreaGuideRecord,
    PropertyMediaRecord,
    PropertyRecord,
    StaffUserRecord,
)

DEV_PROPERTIES = [
    {
        "id": "PROP-ISB-001",
        "slug": "1-kanal-modern-luxury-villa-dha-phase-2-islamabad",
        "title": "1 Kanal Modern Luxury Villa with Landscaped Lawn",
        "description": "Exquisite 1 Kanal designer residence in DHA Phase 2 Sector B. Featuring 5 master ensuite bedrooms, double-height foyer, imported Turkish kitchen, Spanish tile accents, private landscaped lawn, and servant quarters. Complete CDA and DHA transfer allotment with zero encumbrances.",
        "transaction_type": "sale",
        "property_type": "house",
        "city": "Islamabad",
        "area": "DHA Phase 2",
        "price_pkr": 78000000,
        "bedrooms": 5,
        "bathrooms": 6,
        "size_sqft": 4500,
        "developer": "Habib Modern Homes",
        "payment_plan": "100% upfront clear bank pay order transfer",
        "amenities": ["Private Lawn", "Imported Kitchen", "Smart Home Automation", "Solar Net Metering", "Servant Quarter", "24/7 Gated Security", "CCTV Surveillance"],
        "investment_goals": ["Luxury Living", "Capital Appreciation"],
        "nearby_schools": ["Roots Ivy International", "Army Public School DHA"],
        "nearby_hospitals": ["DHA Medical Center", "Al-Shifa Eye Trust"],
        "latitude": 33.5283,
        "longitude": 73.1517,
        "photos": [
            ("https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80", "Exterior facade with manicured lawn"),
            ("https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=1200&q=80", "Grand living room with double height ceiling"),
            ("https://images.unsplash.com/photo-1600585152220-90363fe7e115?auto=format&fit=crop&w=1200&q=80", "Gourmet kitchen with island"),
        ],
    },
    {
        "id": "PROP-ISB-002",
        "slug": "corner-executive-penthouse-suite-f10-islamabad",
        "title": "Corner Executive Penthouse Suite with Margalla Hills View",
        "description": "High-floor duplex penthouse in Sector F-10 with breathtaking unobstructed views of the Margalla National Park. 3 expansive bedroom suites, private terrace lounge, central VRF climate control, 100% standby power generator, and 2 dedicated basement parking slots.",
        "transaction_type": "rent",
        "property_type": "apartment",
        "city": "Islamabad",
        "area": "F-10",
        "price_pkr": 220000,
        "bedrooms": 3,
        "bathrooms": 3,
        "size_sqft": 2800,
        "developer": "Margalla Skyline Towers",
        "payment_plan": "Quarterly rent advance with 2 months refundable security deposit",
        "amenities": ["Margalla Hills View", "Private Terrace", "Central AC", "100% Standby Generator", "2 Underground Parking Slots", "High-speed Passenger Elevators", "Concierge Lobby"],
        "investment_goals": ["Executive Rental", "Diplomatic Lease"],
        "nearby_schools": ["Froebel's International", "Headstart School F-10"],
        "nearby_hospitals": ["Maroof International Hospital F-10", "PAF Hospital"],
        "latitude": 33.6934,
        "longitude": 73.0112,
        "photos": [
            ("https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80", "Living salon with panoramic mountain views"),
            ("https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80", "Private rooftop deck terrace"),
        ],
    },
    {
        "id": "PROP-ISB-003",
        "slug": "10-marla-mediterranean-residence-bahria-town-phase-7",
        "title": "10 Marla Mediterranean Residence near River View Commercial",
        "description": "Architect-designed 10 Marla luxury residence located in Bahria Town Phase 7 near River View. 4 spacious ensuite bedrooms, designer sanitary fixtures, solid ash wood doors, rooftop BBQ pavilion, and underground water reservoir. Uninterrupted power and civic amenities.",
        "transaction_type": "sale",
        "property_type": "house",
        "city": "Rawalpindi",
        "area": "Bahria Town Phase 7",
        "price_pkr": 34000000,
        "bedrooms": 4,
        "bathrooms": 4,
        "size_sqft": 2250,
        "developer": "Bahria Town Private Developments",
        "payment_plan": "Full payment direct transfer via Bahria Head Office",
        "amenities": ["Zero Load Shedding", "Ash Wood Doors", "Rooftop BBQ Area", "Gated Security", "Broadband Fiber Ready", "Walk to Civic Park"],
        "investment_goals": ["Family Home", "Rental Yield"],
        "nearby_schools": ["Roots Millennium Bahria Phase 7", "Beaconhouse"],
        "nearby_hospitals": ["Bahria International Hospital", "Reliance Hospital"],
        "latitude": 33.5421,
        "longitude": 73.1098,
        "photos": [
            ("https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80", "Mediterranean villa exterior"),
            ("https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=1200&q=80", "Modern interior foyer and dining room"),
        ],
    },
    {
        "id": "PROP-ISB-004",
        "slug": "prime-commercial-corporate-floor-gulberg-greens",
        "title": "Prime Corporate Office Floor with Dedicated High-Speed Elevators",
        "description": "Grade-A corporate floor in Gulberg Greens commercial zone along Islamabad Expressway. 4,200 sq ft open-plan shell-and-core space suitable for multinational headquarters, tech firms, or financial institutions. CDA-compliant fire safety, central HVAC, and 4 dedicated parking bays.",
        "transaction_type": "rent",
        "property_type": "office",
        "city": "Islamabad",
        "area": "Gulberg Greens",
        "price_pkr": 450000,
        "bedrooms": 0,
        "bathrooms": 4,
        "size_sqft": 4200,
        "developer": "Gulberg Corporate Tower Developers",
        "payment_plan": "Bi-annual commercial lease agreement with bank guarantee",
        "amenities": ["Grade A Office Space", "High Speed Fiber", "Direct Expressway Access", "Dedicated Basement Parking", "Backup Diesel Generators", "Fire Suppression System"],
        "investment_goals": ["Commercial Head Office", "High Rental Yield"],
        "nearby_schools": ["Froebels Gulberg", "Roots Millennium"],
        "nearby_hospitals": ["Gulberg Medical Center", "KRL Hospital"],
        "latitude": 33.6012,
        "longitude": 73.1345,
        "photos": [
            ("https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=80", "Corporate floor with floor-to-ceiling glass"),
            ("https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1200&q=80", "Modern executive conference suite"),
        ],
    },
    {
        "id": "PROP-ISB-005",
        "slug": "2-kanal-diplomatic-enclave-signature-villa-f7",
        "title": "2 Kanal Diplomatic Enclave Signature Villa in Sector F-7",
        "description": "Rarely available 2 Kanal ambassadorial estate in Sector F-7/2 Islamabad. Features 6 luxurious master suites, heated indoor lap pool, bullet-resistant security guard post, embassy-grade boundary walls, basement cinema, and landscaped formal rose gardens. 100% CDA audited title.",
        "transaction_type": "sale",
        "property_type": "house",
        "city": "Islamabad",
        "area": "F-7",
        "price_pkr": 240000000,
        "bedrooms": 6,
        "bathrooms": 7,
        "size_sqft": 9000,
        "developer": "Capital Signature Residences",
        "payment_plan": "Direct CDA allotment transfer with bank escrow",
        "amenities": ["Indoor Heated Swimming Pool", "Embassy-Grade Security", "Private Home Cinema", "Landscaped Gardens", "Guard Post", "Solar 30kW System", "Italian Kitchen"],
        "investment_goals": ["Diplomatic Mission", "Generational Luxury Asset"],
        "nearby_schools": ["International School of Islamabad (ISOI)", "Super Nova F-7"],
        "nearby_hospitals": ["Ali Medical Center F-8", "Kulsum International Hospital Blue Area"],
        "latitude": 33.7225,
        "longitude": 73.0567,
        "photos": [
            ("https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80", "Grand villa exterior with pool terrace"),
            ("https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1200&q=80", "Master bedroom retreat with terrace"),
        ],
    },
    {
        "id": "PROP-ISB-006",
        "slug": "modern-2-bed-serviced-residence-clifton-blue-area",
        "title": "Modern 2-Bed Serviced Luxury Apartment in Blue Area",
        "description": "Elegantly finished 2-bedroom serviced apartment in Islamabad's thriving Blue Area business district. Walking distance to Metro bus terminal, Jinnah Super Market, and corporate offices. Fully furnished with European kitchen, smart electronic door locks, and 24/7 reception desk.",
        "transaction_type": "rent",
        "property_type": "apartment",
        "city": "Islamabad",
        "area": "Blue Area",
        "price_pkr": 160000,
        "bedrooms": 2,
        "bathrooms": 2,
        "size_sqft": 1450,
        "developer": "Centaurus Corporate & Residential",
        "payment_plan": "Quarterly rent advance via official bank transfer",
        "amenities": ["Fully Furnished", "Reception Concierge", "Smart Lock Entry", "Standby Generator", "Metro Bus Connectivity", "Basement Parking"],
        "investment_goals": ["Corporate Professional Lease", "Short-stay Rental"],
        "nearby_schools": ["Islamabad Model College F-6", "Froebels"],
        "nearby_hospitals": ["Kulsum International Hospital", "PIMS Hospital"],
        "latitude": 33.7104,
        "longitude": 73.0645,
        "photos": [
            ("https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80", "Elegantly styled living room"),
            ("https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1200&q=80", "Contemporary open kitchen and dining"),
        ],
    },
]


def seed() -> None:
    from app.core.config import settings
    if settings.app_env != "development":
        raise RuntimeError("Demo fixtures are development only")
    create_schema_for_local_development()
    now = datetime.now(UTC)

    with SessionLocal.begin() as session:
        # Create default staff user if not present
        staff = session.get(StaffUserRecord, "staff-awaaz-admin")
        if not staff:
            session.add(
                StaffUserRecord(
                    provider_subject="staff-awaaz-admin",
                    email="advisory@awaazestate.pk",
                    display_name="Awaaz Advisory Desk",
                    role="administrator",
                    is_active=True,
                )
            )

        for p_data in DEV_PROPERTIES:
            existing = session.get(PropertyRecord, p_data["id"])
            if not existing:
                prop = PropertyRecord(
                    id=p_data["id"],
                    slug=p_data["slug"],
                    title=p_data["title"],
                    description=p_data["description"],
                    transaction_type=p_data["transaction_type"],
                    property_type=p_data["property_type"],
                    city=p_data["city"],
                    area=p_data["area"],
                    purpose=p_data["transaction_type"],
                    price_pkr=p_data["price_pkr"],
                    bedrooms=p_data["bedrooms"],
                    bathrooms=p_data["bathrooms"],
                    size_sqft=p_data["size_sqft"],
                    amenities=p_data["amenities"],
                    investment_goals=p_data["investment_goals"],
                    nearby_schools=p_data["nearby_schools"],
                    nearby_hospitals=p_data["nearby_hospitals"],
                    developer=p_data["developer"],
                    payment_plan=p_data["payment_plan"],
                    available=True,
                    assigned_employee="Awaaz Advisory Team",
                    assigned_staff_id="staff-awaaz-admin",
                    source_version="v1",
                    source="development-fixture",
                    publication_status="published",
                    availability_status="available",
                    availability_confirmed_at=now,
                    content_permission_confirmed_at=now,
                    published_at=now,
                    latitude=p_data["latitude"],
                    longitude=p_data["longitude"],
                )
                session.add(prop)

                for idx, (photo_url, alt) in enumerate(p_data["photos"]):
                    media = PropertyMediaRecord(
                        id=str(uuid4()),
                        property_id=p_data["id"],
                        original_object_path=f"properties/{p_data['id']}/photo_{idx}.jpg",
                        derivative_object_path=f"properties/{p_data['id']}/photo_{idx}_thumb.jpg",
                        public_url=photo_url,
                        alt_text=alt,
                        sort_order=idx,
                        processing_status="ready",
                        is_public=True,
                    )
                    session.add(media)
            else:
                # Update existing record
                existing.slug = p_data["slug"]
                existing.title = p_data["title"]
                existing.description = p_data["description"]
                existing.transaction_type = p_data["transaction_type"]
                existing.property_type = p_data["property_type"]
                existing.city = p_data["city"]
                existing.area = p_data["area"]
                existing.price_pkr = p_data["price_pkr"]
                existing.bedrooms = p_data["bedrooms"]
                existing.bathrooms = p_data["bathrooms"]
                existing.size_sqft = p_data["size_sqft"]
                existing.amenities = p_data["amenities"]
                existing.investment_goals = p_data["investment_goals"]
                existing.developer = p_data["developer"]
                existing.payment_plan = p_data["payment_plan"]
                existing.source = "development-fixture"
                existing.available = True
                existing.publication_status = "published"
                existing.availability_status = "available"
                existing.availability_confirmed_at = now
                existing.published_at = now
                existing.latitude = p_data["latitude"]
                existing.longitude = p_data["longitude"]

    print(f"Successfully seeded {len(DEV_PROPERTIES)} verified properties with media!")


DEV_AREA_GUIDES = [
    {
        "id": "GUIDE-ISB-001",
        "city_slug": "islamabad",
        "area_slug": "dha-phase-2",
        "title": "DHA Phase 2, Islamabad",
        "overview_markdown": "DHA Phase 2 is an established master-planned gated enclave located along the Grand Trunk Road and Islamabad Expressway. Developed by the Defence Housing Authority, it offers secure, structured residential sectors with round-the-clock surveillance, landscaped central parks, and dedicated commercial districts.",
        "amenities_summary": "Features Giga Mall, DHA Club, Jacaranda Family Club, commercial banks, international fast-food chains, family parks, and state-of-the-art emergency medical centers.",
        "transport_info": "Direct access to GT Road (N-5) and the signal-free Islamabad Expressway corridor, providing convenient transit to downtown Islamabad and Rawalpindi Cantt.",
        "investment_outlook": "High rental demand from corporate executives and overseas Pakistanis, with strong long-term capital preservation due to verified institutional allotment records.",
        "sources": [
            {"title": "DHA Islamabad-Rawalpindi Official Portal", "url": "https://dhai-r.com.pk"},
            {"title": "Survey of Pakistan National Cartographic Registry", "url": "https://surveyofpakistan.gov.pk"},
        ],
    },
    {
        "id": "GUIDE-ISB-002",
        "city_slug": "islamabad",
        "area_slug": "f-7",
        "title": "Sector F-7, Islamabad",
        "overview_markdown": "Sector F-7 is one of Islamabad's most prestigious CDA-planned residential sectors, positioned at the foothills of the Margalla Hills. Characterized by wide tree-lined boulevards and high-value single-family villas, F-7 houses prominent diplomats, senior executives, and established families.",
        "amenities_summary": "Home to the famous Jinnah Super Market (F-7 Markaz), boutique cafes, fine dining establishments, embassies, and elite international schools.",
        "transport_info": "Bordered by Faisal Avenue and Margalla Road, offering rapid connectivity to the Diplomatic Enclave, Secretariat, and Blue Area commercial spine.",
        "investment_outlook": "Prime capital asset class with consistent historic appreciation and premium diplomatic rental yields.",
        "sources": [
            {"title": "Capital Development Authority (CDA) Sector Plan", "url": "https://cda.gov.pk"},
            {"title": "Islamabad Master Plan Archives", "url": "https://cda.gov.pk"},
        ],
    },
    {
        "id": "GUIDE-ISB-003",
        "city_slug": "islamabad",
        "area_slug": "f-10",
        "title": "Sector F-10, Islamabad",
        "overview_markdown": "Sector F-10 is a vibrant CDA sector in Zone 1 offering high-end residential houses, executive apartment complexes, and a thriving commercial hub. It borders the historic Fatima Jinnah Park (F-9 Park).",
        "amenities_summary": "Surrounded by F-10 Markaz commercial center, Maroof International Hospital, leading bank headquarters, and direct foot-access to F-9 Park.",
        "transport_info": "Direct arterial connectivity via Margalla Road, Ibn-e-Sina Road, and Srinagar Highway.",
        "investment_outlook": "Steady residential rental yields with robust demand for luxury apartments and duplex penthouses.",
        "sources": [
            {"title": "Capital Development Authority (CDA) Zone 1 Layout", "url": "https://cda.gov.pk"},
        ],
    },
    {
        "id": "GUIDE-RWP-001",
        "city_slug": "rawalpindi",
        "area_slug": "bahria-town-phase-7",
        "title": "Bahria Town Phase 7, Rawalpindi",
        "overview_markdown": "Bahria Town Phase 7 is a fully self-contained master-planned riverfront community located on the banks of the Soan River. It features underground civic cabling, dedicated private security patrols, and uninterrupted utility infrastructure.",
        "amenities_summary": "Features River View Commercial arcade, Greenvalley Hypermarket, Safari Club, international schools, dining promenades, and landscaped family parks.",
        "transport_info": "Interconnected via Bahria Expressway to GT Road and Wilayat Complex, with upcoming access to the Rawalpindi Ring Road.",
        "investment_outlook": "Active secondary market with accessible entry price points relative to CDA sectors, delivering robust rental occupancy.",
        "sources": [
            {"title": "Rawalpindi Development Authority (RDA) Civic Registry", "url": "https://rda.gop.pk"},
        ],
    },
    {
        "id": "GUIDE-ISB-004",
        "city_slug": "islamabad",
        "area_slug": "gulberg-greens",
        "title": "Gulberg Greens, Islamabad",
        "overview_markdown": "Gulberg Greens is an exclusive agro-farming housing scheme developed by IBECHS, designed around lush 4, 5, and 10 Kanal farmhouse estates and a modern corporate commercial spine.",
        "amenities_summary": "Features Gulberg Mall, Karakoram Enclave, central green belts, underground electrification, and luxury club facilities.",
        "transport_info": "Direct dedicated interchange on the Islamabad Expressway, connecting to Zero Point in under 15 minutes and direct link to Islamabad Airport.",
        "investment_outlook": "High capital growth potential for corporate offices and agro-residential farmhouses.",
        "sources": [
            {"title": "Capital Development Authority (CDA) Housing Societies Register", "url": "https://cda.gov.pk"},
        ],
    },
    {
        "id": "GUIDE-ISB-005",
        "city_slug": "islamabad",
        "area_slug": "blue-area",
        "title": "Blue Area Commercial Corridor, Islamabad",
        "overview_markdown": "Blue Area is the central business district (CBD) of Islamabad, stretching along Jinnah Avenue. It hosts headquarters of multinational corporations, telecom giants, commercial banks, and federal institutions.",
        "amenities_summary": "Grade-A corporate floor plates, central retail plazas, banks, restaurants, executive business centers, and transit stations.",
        "transport_info": "Served directly by the Metro Bus rapid transit corridor and Jinnah Avenue, connecting east and west Islamabad.",
        "investment_outlook": "The highest commercial rental yields in the capital territory with blue-chip institutional tenants.",
        "sources": [
            {"title": "CDA Commercial Directorate Regulations", "url": "https://cda.gov.pk"},
        ],
    },
]


def seed_guides() -> None:
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        for g_data in DEV_AREA_GUIDES:
            existing = session.query(AreaGuideRecord).filter_by(
                city_slug=g_data["city_slug"],
                area_slug=g_data["area_slug"],
            ).first()
            if not existing:
                guide = AreaGuideRecord(
                    id=g_data["id"],
                    city_slug=g_data["city_slug"],
                    area_slug=g_data["area_slug"],
                    title=g_data["title"],
                    overview_markdown=g_data["overview_markdown"],
                    amenities_summary=g_data["amenities_summary"],
                    transport_info=g_data["transport_info"],
                    investment_outlook=g_data["investment_outlook"],
                    publication_status="published",
                    reviewed_at=now,
                    reviewer_id="staff-audit-lead",
                    sources_json=g_data["sources"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(guide)
            else:
                existing.title = g_data["title"]
                existing.overview_markdown = g_data["overview_markdown"]
                existing.amenities_summary = g_data["amenities_summary"]
                existing.transport_info = g_data["transport_info"]
                existing.investment_outlook = g_data["investment_outlook"]
                existing.publication_status = "published"
                existing.reviewed_at = now
                existing.sources_json = g_data["sources"]
                existing.updated_at = now
    print(f"Successfully seeded {len(DEV_AREA_GUIDES)} reviewed area guides!")


if __name__ == "__main__":
    seed()
    seed_guides()
