using System;
using System.Collections.Generic;
using System.Linq;

namespace StudentTracker
{
    public class Program
    {
        public class Student
        {
            public string Name { get; set; }
            public int LateCount { get; set; }
            public int Points { get; set; }
            public int DetentionsServed { get; set; }
            public bool NeedsDetention => Points >= 100;

            public Student(string name)
            {
                Name = name;
                LateCount = 0;
                Points = 0;
                DetentionsServed = 0;
            }
        }

        static List<Student> Students = new List<Student>
        {
            new Student("Abdirahman"),
            new Student("Alexander"),
            new Student("Alexandre"),
            new Student("Ali"),
            new Student("Ben"),
            new Student("Deshi"),
            new Student("Fidel"),
            new Student("Haaroon"),
            new Student("Jakub"),
            new Student("Kadija"),
            new Student("Karl-Hendz"),
            new Student("Mohamed"),
            new Student("Mohamed Houssam")
        };

        static void Main(string[] args)
        {
            bool quit = false;

            while (!quit)
            {
                DisplayStudents();
                DisplayMenu();

                string input = Console.ReadLine();
                if (int.TryParse(input, out int choice))
                {
                    switch (choice)
                    {
                        case 1:
                            AddLate();
                            break;
                        case 2:
                            CheckDetentions();
                            break;
                        case 3:
                            ConfirmDetention();
                            break;
                        case 4:
                            AddNewStudent();
                            break;
                        case 5:
                            quit = true;
                            break;
                        default:
                            Console.WriteLine("Invalid choice. Please try again.");
                            break;
                    }
                }
                else
                {
                    Console.WriteLine("Please enter a valid number.");
                }
            }
        }

        static void DisplayMenu()
        {
            Console.WriteLine("\nMenu:");
            Console.WriteLine("1. Add a late arrival for a student");
            Console.WriteLine("2. Check who needs detention");
            Console.WriteLine("3. Confirm a detention served");
            Console.WriteLine("4. Add a new student");
            Console.WriteLine("5. Exit");
            Console.Write("Your choice: ");
        }

        static void DisplayStudents()
        {
            Console.WriteLine("\nStudents and Points:");
            Console.WriteLine("-----------------------");
            Console.WriteLine($"{"Name",-15} {"Lates",-15} {"Points",-10} {"Detentions",-15}");
            Console.WriteLine(new string('-', 55));

            foreach (var student in Students.OrderBy(e => e.Name))
            {
                Console.WriteLine($"{student.Name,-15} {student.LateCount,-15} {student.Points,-10} {student.DetentionsServed,-15}");
            }
        }

        static void AddLate()
        {
            Console.Write("\nEnter student name: ");
            string name = Console.ReadLine();
            var student = Students.FirstOrDefault(e => e.Name.Equals(name, StringComparison.OrdinalIgnoreCase));

            if (student != null)
            {
                Console.Write("Enter minutes late: ");
                if (int.TryParse(Console.ReadLine(), out int minutesLate))
                {
                    int points = CalculatePoints(minutesLate);
                    student.LateCount++;
                    student.Points += points;
                    Console.WriteLine($"\n{student.Name} was {minutesLate} minutes late. {points} points added.");
                }
                else
                {
                    Console.WriteLine("\nInvalid input for minutes.");
                }
            }
            else
            {
                Console.WriteLine("\nStudent not found.");
            }
        }

        static void CheckDetentions()
        {
            var needsDetention = Students.Where(e => e.NeedsDetention);

            Console.WriteLine("\nStudents needing detention:");
            Console.WriteLine("-------------------------------------");

            if (!needsDetention.Any())
            {
                Console.WriteLine("None.");
            }
            else
            {
                foreach (var student in needsDetention)
                {
                    Console.WriteLine($"{student.Name,-15} {student.Points,-10} {student.DetentionsServed,-15}");
                }
            }
        }

        static void ConfirmDetention()
        {
            Console.Write("\nEnter student name: ");
            string name = Console.ReadLine();
            var student = Students.FirstOrDefault(e => e.Name.Equals(name, StringComparison.OrdinalIgnoreCase));

            if (student != null)
            {
                if (student.NeedsDetention)
                {
                    student.Points -= 100;
                    student.DetentionsServed++;
                    Console.WriteLine($"\nDetention confirmed for {student.Name}. 100 points removed.");
                }
                else
                {
                    Console.WriteLine($"\n{student.Name} does not need detention.");
                }
            }
            else
            {
                Console.WriteLine("\nStudent not found.");
            }
        }

        static void AddNewStudent()
        {
            Console.Write("\nEnter new student name: ");
            string name = Console.ReadLine();

            if (string.IsNullOrWhiteSpace(name))
            {
                Console.WriteLine("\nName cannot be empty.");
                return;
            }

            if (Students.Any(e => e.Name.Equals(name, StringComparison.OrdinalIgnoreCase)))
            {
                Console.WriteLine("\nStudent already exists.");
            }
            else
            {
                Students.Add(new Student(name));
                Console.WriteLine($"\nStudent {name} added.");
            }
        }

        static int CalculatePoints(int minutesLate)
        {
            if (minutesLate <= 1)
                return 0;
            if (minutesLate <= 7)
                return (minutesLate - 1) * 1;
            if (minutesLate <= 27)
                return (minutesLate - 7) * 2 + 6;
            if (minutesLate <= 45)
                return (minutesLate - 27) * 3 + 46;
            return 100;
        }
    }
}