
from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def add_data():
    with app.app_context():
        # Get the ICD2O course
        course = Course.query.filter_by(code='ICD2O').first()
        if not course:
            print("ICD2O course not found. Please run import_icd2o_curriculum.py first.")
            return

        while True:
            print("\nManual Data Input Menu:")
            print("1. Add Strand")
            print("2. Add Overall Expectation")
            print("3. Add Specific Expectation")
            print("4. Exit")
            
            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                code = input("Enter strand code (e.g., A, B, C): ")
                title_en = input("Enter strand title in English: ")
                title_fr = input("Enter strand title in French: ")
                
                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_en=title_en,
                    title_fr=title_fr
                )
                db.session.add(strand)
                
            elif choice == '2':
                strand_code = input("Enter strand code (e.g., A, B, C): ")
                strand = Strand.query.filter_by(course_id=course.id, code=strand_code).first()
                if not strand:
                    print("Strand not found")
                    continue
                    
                code = input("Enter overall expectation code (e.g., A1, B2): ")
                desc_en = input("Enter description in English: ")
                desc_fr = input("Enter description in French: ")
                
                overall = OverallExpectation(
                    strand_id=strand.id,
                    code=code,
                    description_en=desc_en,
                    description_fr=desc_fr
                )
                db.session.add(overall)
                
            elif choice == '3':
                overall_code = input("Enter overall expectation code (e.g., A1, B2): ")
                overall = OverallExpectation.query.join(Strand).filter(
                    Strand.course_id == course.id,
                    OverallExpectation.code == overall_code
                ).first()
                if not overall:
                    print("Overall expectation not found")
                    continue
                    
                code = input("Enter specific expectation code (e.g., A1.1, B2.1): ")
                desc_en = input("Enter description in English: ")
                desc_fr = input("Enter description in French: ")
                
                specific = SpecificExpectation(
                    overall_expectation_id=overall.id,
                    code=code,
                    description_en=desc_en,
                    description_fr=desc_fr
                )
                db.session.add(specific)
                
            elif choice == '4':
                break
                
            try:
                db.session.commit()
                print("Data added successfully!")
            except Exception as e:
                print(f"Error: {str(e)}")
                db.session.rollback()

if __name__ == '__main__':
    add_data()
