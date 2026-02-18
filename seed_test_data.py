from database import SessionLocal
from models import User, AcademicMapping, Subject, Class, UserRole
from auth import hash_password

db = SessionLocal()

def seed():
    # 1. Ensure Subject exists
    subj = db.query(Subject).filter(Subject.name == "Mathematics").first()
    if not subj:
        subj = Subject(name="Mathematics", code="MATH101")
        db.add(subj)
        db.flush()

    # 2. Ensure Class exists
    cls = db.query(Class).filter(Class.name == "10A").first()
    if not cls:
        cls = Class(name="10A", class_level="10", section="A")
        db.add(cls)
        db.flush()

    # 3. Ensure Teacher exists
    teacher = db.query(User).filter(User.email == "smith@school.com").first()
    if not teacher:
        teacher = User(
            full_name="Mr. Smith",
            email="smith@school.com",
            password_hash=hash_password("pass123"),
            role=UserRole.teacher
        )
        db.add(teacher)
        db.flush()

    # 4. Ensure Student exists
    student = db.query(User).filter(User.email == "john@school.com").first()
    if not student:
        student = User(
            full_name="John Student",
            email="john@school.com",
            password_hash=hash_password("pass123"),
            role=UserRole.student,
            class_id=cls.id
        )
        db.add(student)
        db.flush()

    # 5. Ensure Parent exists
    parent = db.query(User).filter(User.email == "doe@school.com").first()
    if not parent:
        parent = User(
            full_name="Mrs. Doe",
            email="doe@school.com",
            password_hash=hash_password("pass123"),
            role=UserRole.parent
        )
        db.add(parent)
        db.flush()
        parent.children.append(student)

    # 6. Ensure Mapping exists
    mapping = db.query(AcademicMapping).filter(
        AcademicMapping.teacher_id == teacher.id,
        AcademicMapping.class_id == cls.id
    ).first()
    if not mapping:
        mapping = AcademicMapping(
            teacher_id=teacher.id,
            class_id=cls.id,
            subject_id=subj.id
        )
        db.add(mapping)

    db.commit()
    print("✅ Test data seeded successfully")

if __name__ == "__main__":
    seed()
    db.close()
