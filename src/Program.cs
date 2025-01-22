using System;

class Program 
{
    static void Main() 
    {
        try 
        {
            Console.WriteLine("Enter your name:");
            string? name = Console.ReadLine();
            if (!string.IsNullOrEmpty(name))
            {
                Console.WriteLine($"Hello, {name}!");
            }
            else 
            {
                Console.WriteLine("No name entered.");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }
    }
}