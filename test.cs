using System;
using System.Globalization;
using System.Linq;

class Program 
{
    static void Main() 
    {
        try
        {
            // Test Unicode strings
            string unicodeText = "Hello • こんにちは • Bonjour";
            Console.WriteLine($"Unicode test: {unicodeText}");

            // Test array operations
            int[] numbers = { 1, 2, 3, 4, 5 };
            double average = numbers.Average();
            Console.WriteLine($"Array average: {average:F2}");

            // Test culture-specific formatting
            double amount = 1234567.89;
            Console.WriteLine($"Currency format: {amount:C2}");

            // Test exception handling
            object nullObj = null;
            try 
            {
                Console.WriteLine(nullObj.ToString());
            }
            catch (NullReferenceException)
            {
                Console.WriteLine("Successfully caught null reference exception");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}