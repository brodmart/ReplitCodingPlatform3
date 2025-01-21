using System;
using System.Collections.Generic;
using System.Linq;

public class Program 
{
    static void Main(string[] args)
    {
        try 
        {
            Console.WriteLine("Starting large code test...");

            // Initialize test data
            var numbers = Enumerable.Range(1, 1000).ToList();

            // Perform some computations
            var sum = numbers.Sum();
            var avg = numbers.Average();

            Console.WriteLine($"Sum: {sum}");
            Console.WriteLine($"Average: {avg}");
            Console.WriteLine("Test completed successfully!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error occurred: {ex.Message}");
        }
    }
}