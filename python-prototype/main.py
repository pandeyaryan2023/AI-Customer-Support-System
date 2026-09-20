import json
from pathlib import Path

# Keep the data file next to this script, so it is found no matter
# which folder we run the program from.
DATA_FILE = Path(__file__).parent / "complaints.json"

# The only statuses a ticket is allowed to have (from the project synopsis).
VALID_STATUSES = [
    "OPEN",
    "IN_PROGRESS",
    "WAITING_FOR_CUSTOMER",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
]

try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        complaints = json.load(f)
except FileNotFoundError:
    complaints = []


def save_complaints():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(complaints, f, indent=2)


def get_valid_int(prompt):
    while True:
        value = input(prompt)
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid number.")


def find_complaint(ticket_id):
    """Return the complaint with this ID, or None if there is no such ticket."""
    for complaint in complaints:
        if complaint["id"] == ticket_id:
            return complaint
    return None


def create_complaint():
    title = input("Enter complaint title: ")
    description = input("Enter complaint description: ")
    new_id = len(complaints) + 1

    complaint = {
        "id": new_id,
        "title": title,
        "description": description,
        "status": "OPEN"
    }
    complaints.append(complaint)
    save_complaints()
    print(f"Complaint created with Ticket #{new_id}")


def view_complaints():
    for complaint in complaints:
        print(f"Ticket #{complaint['id']} - {complaint['title']}")
        print(f"Description: {complaint['description']}")
        print(f"Status: {complaint['status']}")
        print()


def search_complaint():
    search_id = get_valid_int("Enter ticket ID to search: ")
    complaint = find_complaint(search_id)

    if complaint is None:
        print(f"No complaint found with ID {search_id}")
        return

    print(f"Ticket #{complaint['id']} - {complaint['title']}")
    print(f"Description: {complaint['description']}")
    print(f"Status: {complaint['status']}")


def update_status():
    update_id = get_valid_int("Enter ticket ID to update: ")
    complaint = find_complaint(update_id)

    if complaint is None:
        print(f"No complaint found with ID {update_id}")
        return

    print("Valid statuses:", ", ".join(VALID_STATUSES))
    new_status = input("Enter new status: ").strip().upper().replace(" ", "_")

    if new_status not in VALID_STATUSES:
        print("Invalid status. Nothing was changed.")
        return

    complaint["status"] = new_status
    save_complaints()
    print(f"Updated Ticket #{complaint['id']} - {complaint['title']}")
    print(f"New Status: {complaint['status']}")


while True:
    print("\n--- Complaint Management ---")
    print("1. Create a complaint")
    print("2. View all complaints")
    print("3. Search complaint by ticket ID")
    print("4. Update complaint status")
    print("5. Exit")

    choice = input("Choose an option: ")

    if choice == "1":
        create_complaint()
    elif choice == "2":
        view_complaints()
    elif choice == "3":
        search_complaint()
    elif choice == "4":
        update_status()
    elif choice == "5":
        print("Goodbye!")
        break
    else:
        print("Invalid choice, try again.")
