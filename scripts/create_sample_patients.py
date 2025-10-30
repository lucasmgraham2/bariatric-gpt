"""
Create sample patient data for testing the AI multi-agent system
"""
import psycopg2
from datetime import date, timedelta

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="bariatric_db",
    user="bariatric_user",
    password="bariatric_password"
)

cursor = conn.cursor()

# Create patients table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        age INTEGER,
        surgery_type VARCHAR(255),
        surgery_date DATE,
        current_weight FLOAT,
        starting_weight FLOAT,
        bmi FLOAT,
        status VARCHAR(255)
    );
""")

# Sample patients
sample_patients = [
    {
        "name": "John Smith",
        "age": 42,
        "surgery_type": "Gastric Bypass",
        "surgery_date": date.today() - timedelta(days=180),  # 6 months ago
        "current_weight": 220.0,
        "starting_weight": 310.0,
        "bmi": 32.5,
        "status": "Excellent progress"
    },
    {
        "name": "Sarah Johnson",
        "age": 38,
        "surgery_type": "Sleeve Gastrectomy",
        "surgery_date": date.today() - timedelta(days=365),  # 1 year ago
        "current_weight": 165.0,
        "starting_weight": 250.0,
        "bmi": 27.8,
        "status": "On track"
    },
    {
        "name": "Michael Brown",
        "age": 55,
        "surgery_type": "Gastric Bypass",
        "surgery_date": date.today() - timedelta(days=90),  # 3 months ago
        "current_weight": 275.0,
        "starting_weight": 340.0,
        "bmi": 38.2,
        "status": "Needs nutritional counseling"
    },
    {
        "name": "Emily Davis",
        "age": 33,
        "surgery_type": "Sleeve Gastrectomy",
        "surgery_date": date.today() - timedelta(days=730),  # 2 years ago
        "current_weight": 155.0,
        "starting_weight": 240.0,
        "bmi": 25.1,
        "status": "Maintenance phase"
    }
]

# Insert sample patients
print("Creating sample patient data...")
for patient in sample_patients:
    cursor.execute("""
        INSERT INTO patients (name, age, surgery_type, surgery_date, current_weight, starting_weight, bmi, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (
        patient["name"],
        patient["age"],
        patient["surgery_type"],
        patient["surgery_date"],
        patient["current_weight"],
        patient["starting_weight"],
        patient["bmi"],
        patient["status"]
    ))
    print(f"✅ Created patient: {patient['name']}")

conn.commit()
cursor.close()
conn.close()

print("\n✅ Sample patient data created successfully!")
print("\nTest patient IDs: 1, 2, 3, 4")
print("\nExample AI queries:")
print("- 'What's patient 1's current weight?'")
print("- 'Tell me about patient 2's progress'")
print("- 'Is patient 3's BMI improving?'")
print("- 'What are the best foods after bariatric surgery?'")
