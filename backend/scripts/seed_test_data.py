from backend.database import SessionLocal
from backend.models import User, AcademicMapping, Subject, Class, UserRole
from backend.auth import hash_password

db = SessionLocal()

def seed():
    # 1. Subjects
    subjects_data = [
        ("Mathematics", "MATH101"),
        ("Science", "SCI101"),
        ("English", "ENG101"),
        ("History", "HIS101"),
        ("Computer Science", "CS101"),
    ]
    subjects = {}
    for name, code in subjects_data:
        subj = db.query(Subject).filter(Subject.name == name).first()
        if not subj:
            subj = Subject(name=name, code=code)
            db.add(subj)
            db.flush()
        subjects[name] = subj

    # 2. Classes
    classes_data = [
        ("10A", "10", "A"),
        ("10B", "10", "B"),
        ("11A", "11", "A"),
        ("12A", "12", "A"),
    ]
    classes = {}
    for name, level, section in classes_data:
        cls = db.query(Class).filter(Class.name == name).first()
        if not cls:
            cls = Class(name=name, class_level=level, section=section)
            db.add(cls)
            db.flush()
        classes[name] = cls

    # 3. Teachers
    teachers_data = [
        ("Mr. Smith", "smith@school.com"),
        ("Ms. Johnson", "johnson@school.com"),
        ("Dr. Brown", "brown@school.com"),
    ]
    teachers = {}
    for name, email in teachers_data:
        teacher = db.query(User).filter(User.email == email).first()
        if not teacher:
            teacher = User(
                full_name=name,
                email=email,
                password_hash=hash_password("pass123"),
                role=UserRole.teacher
            )
            db.add(teacher)
            db.flush()
        teachers[email] = teacher

    # 4. Students
    students_data = [
        ("John Student", "john@school.com", "10A"),
        ("Jane Doe", "jane@school.com", "10A"),
        ("Alice Cooper", "alice@school.com", "10B"),
        ("Bob Marley", "bob@school.com", "11A"),
    ]
    students = {}
    for name, email, cls_name in students_data:
        student = db.query(User).filter(User.email == email).first()
        if not student:
            student = User(
                full_name=name,
                email=email,
                password_hash=hash_password("pass123"),
                role=UserRole.student,
                class_id=classes[cls_name].id
            )
            db.add(student)
            db.flush()
        students[email] = student

    # 5. Parents
    parents_data = [
        ("Robert Student", "robert@school.com", ["john@school.com"]),
        ("Mary Doe", "mary@school.com", ["jane@school.com"]),
    ]
    for name, email, children_emails in parents_data:
        parent = db.query(User).filter(User.email == email).first()
        if not parent:
            parent = User(
                full_name=name,
                email=email,
                password_hash=hash_password("pass123"),
                role=UserRole.parent
            )
            db.add(parent)
            db.flush()
            for child_email in children_emails:
                parent.children.append(students[child_email])

    # 6. Mappings (Teacher-Subject-Class)
    mappings_data = [
        ("smith@school.com", "Mathematics", "10A"),
        ("johnson@school.com", "Science", "10A"),
        ("brown@school.com", "Computer Science", "11A"),
    ]
    for t_email, s_name, c_name in mappings_data:
        t = teachers[t_email]
        s = subjects[s_name]
        c = classes[c_name]
        mapping = db.query(AcademicMapping).filter(
            AcademicMapping.teacher_id == t.id,
            AcademicMapping.class_id == c.id,
            AcademicMapping.subject_id == s.id
        ).first()
        if not mapping:
            mapping = AcademicMapping(
                teacher_id=t.id,
                class_id=c.id,
                subject_id=s.id
            )
            db.add(mapping)

    db.commit()
    print("✅ Test data seeded successfully")

if __name__ == "__main__":
    seed()
    db.close()
