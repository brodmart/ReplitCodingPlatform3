using System;

namespace TestInteractive {
    class Program {
        static void Main() {
            Console.WriteLine("What is your name?");
            string name = Console.ReadLine();
            Console.WriteLine($"Hello, {name}! Nice to meet you.");

            Console.WriteLine("Enter your age:");
            string age = Console.ReadLine();
            Console.WriteLine($"You are {age} years old.");
        }
    }
}