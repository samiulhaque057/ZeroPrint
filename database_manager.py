import sqlite3
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='challenges.db'):
        self.db_path = db_path
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def view_all_data(self):
        """View all data in the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print("=== CURRENT DATABASE CONTENTS ===\n")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"--- {table_name.upper()} ---")
            
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if rows:
                for row in rows:
                    print(f"  {row}")
            else:
                print("  (empty)")
            print()
        
        conn.close()
    
    def add_challenge(self, title, description, challenge_type, target_value, target_unit, points_reward, badge_icon="🏆"):
        """Add a new challenge to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO challenges (title, description, challenge_type, target_value, target_unit, 
                                     points_reward, badge_icon, start_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, challenge_type, target_value, target_unit, 
                  points_reward, badge_icon, datetime.now(), True))
            
            conn.commit()
            print(f"✅ Challenge '{title}' added successfully!")
            
        except Exception as e:
            print(f"❌ Error adding challenge: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def update_challenge(self, challenge_id, **kwargs):
        """Update an existing challenge"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build update query dynamically
        valid_fields = ['title', 'description', 'challenge_type', 'target_value', 
                       'target_unit', 'points_reward', 'badge_icon', 'is_active']
        
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            print("❌ No valid fields to update")
            conn.close()
            return
        
        values.append(challenge_id)
        query = f"UPDATE challenges SET {', '.join(update_fields)} WHERE id = ?"
        
        try:
            cursor.execute(query, values)
            conn.commit()
            print(f"✅ Challenge {challenge_id} updated successfully!")
            
        except Exception as e:
            print(f"❌ Error updating challenge: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def delete_challenge(self, challenge_id):
        """Delete a challenge from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First check if challenge exists
            cursor.execute("SELECT title FROM challenges WHERE id = ?", (challenge_id,))
            challenge = cursor.fetchone()
            
            if not challenge:
                print(f"❌ Challenge with ID {challenge_id} not found")
                return
            
            # Delete the challenge
            cursor.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))
            conn.commit()
            print(f"✅ Challenge '{challenge[0]}' (ID: {challenge_id}) deleted successfully!")
            
        except Exception as e:
            print(f"❌ Error deleting challenge: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def add_user(self, email, name):
        """Add a new user to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO users (email, name, created_at)
                VALUES (?, ?, ?)
            """, (email, name, datetime.now()))
            
            conn.commit()
            print(f"✅ User '{name}' ({email}) added successfully!")
            
        except Exception as e:
            print(f"❌ Error adding user: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def join_user_to_challenge(self, user_id, challenge_id):
        """Make a user join a challenge"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user is already in the challenge
            cursor.execute("""
                SELECT id FROM user_challenges 
                WHERE user_id = ? AND challenge_id = ?
            """, (user_id, challenge_id))
            
            if cursor.fetchone():
                print(f"❌ User {user_id} is already in challenge {challenge_id}")
                return
            
            # Add user to challenge
            cursor.execute("""
                INSERT INTO user_challenges (user_id, challenge_id, joined_at)
                VALUES (?, ?, ?)
            """, (user_id, challenge_id, datetime.now()))
            
            conn.commit()
            print(f"✅ User {user_id} joined challenge {challenge_id} successfully!")
            
        except Exception as e:
            print(f"❌ Error joining challenge: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def update_user_progress(self, user_id, challenge_id, progress):
        """Update user's progress on a challenge"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE user_challenges 
                SET current_progress = ?
                WHERE user_id = ? AND challenge_id = ?
            """, (progress, user_id, challenge_id))
            
            if cursor.rowcount == 0:
                print(f"❌ User {user_id} is not in challenge {challenge_id}")
                return
            
            conn.commit()
            print(f"✅ Progress updated to {progress} for user {user_id} in challenge {challenge_id}")
            
        except Exception as e:
            print(f"❌ Error updating progress: {e}")
            conn.rollback()
        finally:
            conn.close()

def main():
    db = DatabaseManager()
    
    while True:
        print("\n" + "="*50)
        print("DATABASE MANAGEMENT TOOL")
        print("="*50)
        print("1. View all data")
        print("2. Add new challenge")
        print("3. Update challenge")
        print("4. Delete challenge")
        print("5. Add new user")
        print("6. Join user to challenge")
        print("7. Update user progress")
        print("8. Export to JSON")
        print("9. Exit")
        print("="*50)
        
        choice = input("Choose an option (1-9): ").strip()
        
        if choice == '1':
            db.view_all_data()
            
        elif choice == '2':
            print("\n--- ADD NEW CHALLENGE ---")
            title = input("Title: ")
            description = input("Description: ")
            challenge_type = input("Type (individual/team/company): ")
            target_value = float(input("Target value: "))
            target_unit = input("Target unit: ")
            points_reward = int(input("Points reward: "))
            badge_icon = input("Badge icon (default: 🏆): ") or "🏆"
            
            db.add_challenge(title, description, challenge_type, target_value, target_unit, points_reward, badge_icon)
            
        elif choice == '3':
            print("\n--- UPDATE CHALLENGE ---")
            challenge_id = int(input("Challenge ID to update: "))
            print("Enter new values (press Enter to skip):")
            
            updates = {}
            title = input("New title: ").strip()
            if title: updates['title'] = title
            
            description = input("New description: ").strip()
            if description: updates['description'] = description
            
            points = input("New points reward: ").strip()
            if points: updates['points_reward'] = int(points)
            
            if updates:
                db.update_challenge(challenge_id, **updates)
            else:
                print("No updates provided")
                
        elif choice == '4':
            challenge_id = int(input("Challenge ID to delete: "))
            confirm = input(f"Are you sure you want to delete challenge {challenge_id}? (yes/no): ")
            if confirm.lower() == 'yes':
                db.delete_challenge(challenge_id)
                
        elif choice == '5':
            print("\n--- ADD NEW USER ---")
            email = input("Email: ")
            name = input("Name: ")
            db.add_user(email, name)
            
        elif choice == '6':
            user_id = int(input("User ID: "))
            challenge_id = int(input("Challenge ID: "))
            db.join_user_to_challenge(user_id, challenge_id)
            
        elif choice == '7':
            user_id = int(input("User ID: "))
            challenge_id = int(input("Challenge ID: "))
            progress = float(input("New progress value: "))
            db.update_user_progress(user_id, challenge_id, progress)
            
        elif choice == '8':
            # Re-run the export script
            import subprocess
            subprocess.run(['python', 'simple_db_view.py'])
            print("✅ Database exported to JSON!")
            
        elif choice == '9':
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
