using System;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Threading;

class Program 
{
    static void Main() 
    {
        try
        {
            Console.OutputEncoding = Encoding.UTF8;
            Console.InputEncoding = Encoding.UTF8;

            // Test console colors
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("Testing console features:");
            Console.ResetColor();

            // Test Unicode output
            Console.WriteLine("Unicode symbols: ★ ■ ● ▲ ▼");

            // Test number formatting
            Console.WriteLine($"Number: {123456.789:N2}");

            // Test console buffer and window
            Console.WriteLine($"Buffer Width: {Console.BufferWidth}");
            Console.WriteLine($"Window Width: {Console.WindowWidth}");

            // Test cursor positioning
            Console.WriteLine("Testing cursor position...");
            Thread.Sleep(500);

            // Basic animation
            for (int i = 0; i < 3; i++)
            {
                Console.Write(".");
                Thread.Sleep(300);
            }
            Console.WriteLine("\nDone!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");
        }
    }
}