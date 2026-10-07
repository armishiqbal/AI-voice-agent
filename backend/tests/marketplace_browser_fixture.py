"""Controlled browser fixture server. Never import this module in application code.
Run with a disposable DATABASE_URL and PYTHONPATH=backend:backend/tests.
"""
from pathlib import Path
from datetime import UTC,datetime
from sqlalchemy import select
from PIL import Image
from app.repositories.database import Base,engine,SessionLocal
from app.repositories.records import OrganizationRecord,MembershipRecord,PropertyRecord,PropertyMediaRecord,StaffUserRecord,LocationRecord
from app.repositories.properties import SqlPropertyRepository
from app.catalog.identity import Identity,require_identity
from app.catalog.staff_auth import StaffPrincipal,require_staff
from app.core.config import settings
from listing_fixtures import import_publishable_demo_properties

if engine.dialect.name!='sqlite' or not str(engine.url.database).startswith('/tmp/awaaz-browser-'):
    raise RuntimeError('Browser fixtures require a named disposable /tmp/awaaz-browser- database')
Base.metadata.create_all(engine)
with SessionLocal() as session:
    populated = session.scalar(select(PropertyRecord.id)) is not None
if not populated:
    import_publishable_demo_properties(SqlPropertyRepository())
with SessionLocal.begin() as session:
    if not session.get(OrganizationRecord,'browser-agency'):
        session.add(OrganizationRecord(id='browser-agency',slug='test-agency',name='TEST ONLY Agency',status='approved',coverage=['Islamabad'],description='Controlled browser fixture. Not real inventory.'))
        session.add(MembershipRecord(id='browser-member',organization_id='browser-agency',subject='browser-agent',display_name='TEST ONLY Agent',email='test@example.com',role='manager',active=True))
        session.add(StaffUserRecord(provider_subject='platform',email='platform@example.com',display_name='TEST ONLY Platform',role='administrator',is_active=True))
    locations=set()
    for p in session.scalars(select(PropertyRecord)).all():
        p.organization_id='browser-agency';p.classification='residential';p.rental_period=None;p.assigned_staff_id='browser-agent';p.assigned_employee='agent:browser-agent';p.source='test-only-evaluation-fixture';p.publication_status='draft';p.availability_status='unavailable';p.available=False
        if p.id=='PROP-001':
            p.city='Islamabad';p.area='TEST ONLY Area';p.title='TEST ONLY · Controlled browser listing';p.description='Test-only demonstration. This is not a real property and is not available.';p.transaction_type='sale';p.purpose='sale';p.property_type='apartment';p.price_pkr=1234567;p.bedrooms=2;p.bathrooms=1;p.size_sqft=1200;p.publication_status='published'
        if p.id=='PROP-001' and (p.city,p.area) not in locations and not session.scalar(select(LocationRecord.id).where(LocationRecord.city==p.city,LocationRecord.area==p.area)):
            locations.add((p.city,p.area))
            session.add(LocationRecord(id='loc-browser-test',city=p.city,city_slug='islamabad',area=p.area,area_slug='test-only-area',reviewed=True))
    for photo in session.scalars(select(PropertyMediaRecord)).all():
        if photo.property_id!='PROP-001':
            photo.public_url=None;photo.is_public=False;photo.processing_status='pending'
            continue
        filename='test-media-prop-001_card.webp';folder=Path(__file__).resolve().parents[1]/'media'/'derivatives';folder.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(800,600),'#e5e9de').save(folder/filename,'WEBP')
        photo.public_url='/media/derivatives/'+filename;photo.derivative_object_path=str(folder/filename);photo.is_public=True;photo.processing_status='ready';photo.alt_text='TEST ONLY demonstration image'
from app.api.app import app
app.dependency_overrides[require_identity]=lambda:Identity('browser-agent','test@example.com','aal2')
app.dependency_overrides[require_staff]=lambda:StaffPrincipal('platform','platform@example.com','Test Platform','administrator')
