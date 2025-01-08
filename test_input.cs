using System;

class Program {
    static void Main() {
        string name;
        int age;
        
        Console.Write("Enter your name: ");
        name = Console.ReadLine();
        
        Console.Write("Enter your age: ");
        age = int.Parse(Console.ReadLine());
        
        Console.WriteLine($"Hello, {name}! You are {age} years old.");
    }
}
