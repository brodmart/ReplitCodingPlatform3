using System;
using System.Globalization;

namespace InvariantTest
{
    class Program 
    {
        static void Main() 
        {
            Console.WriteLine("Testing invariant globalization...");

            // Test number formatting in invariant culture
            double number = 1234.56;
            Console.WriteLine($"Number format: {number:N2}");

            // Test date formatting in invariant culture
            DateTime now = DateTime.Now;
            Console.WriteLine($"Date format: {now:G}");
        }
    }
}