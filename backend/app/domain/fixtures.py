from app.domain.models import Property


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
                # Deliberately spans affordable-to-premium PKR bands for meaningful demo budgets.
                price = (18 + city_index * 6 + purpose_index * 8 + variant * 3) * 1_000_000
                items.append(
                    Property(
                        id=f"DEMO-{number:03d}",
                        title=f"{purpose.title()} opportunity in {areas[variant]}",
                        city=city,
                        area=areas[variant],
                        purpose=purpose,
                        price_pkr=price,
                        bedrooms=0 if purpose == "commercial" else 2 + variant,
                        size_sqft=900 + variant * 450,
                        amenities=["parking", "security", "masjid"],
                        investment_goals=(
                            ["rental yield", "capital appreciation"]
                            if purpose == "investment"
                            else ["capital appreciation"]
                        ),
                        nearby_schools=[f"{city} Model School", f"{areas[variant]} Grammar School"],
                        nearby_hospitals=[
                            f"{city} General Hospital",
                            f"{areas[variant]} Medical Centre",
                        ],
                        developer="Awaaz Demo Developers",
                        payment_plan="Twenty percent booking, flexible installments",
                        available=available,
                        assigned_employee=["Ayesha Khan", "Hamza Ali", "Sara Ahmed"][variant],
                    )
                )
    return items
