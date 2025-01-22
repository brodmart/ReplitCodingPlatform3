using System;

namespace CodingPlatform
{
    public class Program 
    {
        static void Main(string[] args)
        {
            try
            {
                // Basic interactive console functionality
                Console.WriteLine("C# Interactive Console Ready");
                string? input = Console.ReadLine();
                Console.WriteLine($"You entered: {input ?? "nothing"}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
        }
    }
}