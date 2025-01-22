using System;
using System.Collections.Generic;

class Program {
    static void Main() {
        var students = new Dictionary<string, int>();

        while (true) {
            Console.WriteLine("\nStudent Attendance System");
            Console.WriteLine("1. Add Student");
            Console.WriteLine("2. Mark Attendance");
            Console.WriteLine("3. View Attendance");
            Console.WriteLine("4. Exit");

            Console.Write("\nSelect an option: ");
            string choice = Console.ReadLine();

            switch (choice) {
                case "1":
                    Console.Write("Enter student name: ");
                    string name = Console.ReadLine();
                    if (!students.ContainsKey(name)) {
                        students[name] = 0;
                        Console.WriteLine($"Added student: {name}");
                    } else {
                        Console.WriteLine("Student already exists!");
                    }
                    break;

                case "2":
                    Console.Write("Enter student name: ");
                    name = Console.ReadLine();
                    if (students.ContainsKey(name)) {
                        students[name]++;
                        Console.WriteLine($"Marked attendance for {name}");
                    } else {
                        Console.WriteLine("Student not found!");
                    }
                    break;

                case "3":
                    Console.WriteLine("\nAttendance Records:");
                    foreach (var student in students) {
                        Console.WriteLine($"{student.Key}: {student.Value} days");
                    }
                    break;

                case "4":
                    Console.WriteLine("Goodbye!");
                    return;

                default:
                    Console.WriteLine("Invalid option!");
                    break;
            }
        }
    }
}