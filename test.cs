using System;
using System.Collections.Generic;
using System.Linq;

class Program {
    static void Main() {
        // Generate a large array of random numbers
        var random = new Random();
        var numbers = Enumerable.Range(0, 100000).Select(_ => random.Next(1, 1000)).ToList();

        // Perform some computationally intensive operations
        var sorted = numbers.OrderBy(x => x).ToList();
        var filtered = sorted.Where(x => x % 2 == 0).ToList();
        var grouped = filtered.GroupBy(x => x % 10);

        Console.WriteLine($"Original count: {numbers.Count}");
        Console.WriteLine($"Filtered count: {filtered.Count}");
        Console.WriteLine($"Number of groups: {grouped.Count()}");

        // Print first few numbers from each operation
        Console.WriteLine("\nFirst 5 original numbers:");
        numbers.Take(5).ToList().ForEach(x => Console.Write($"{x} "));

        Console.WriteLine("\nFirst 5 sorted numbers:");
        sorted.Take(5).ToList().ForEach(x => Console.Write($"{x} "));

        Console.WriteLine("\nFirst 5 filtered numbers:");
        filtered.Take(5).ToList().ForEach(x => Console.Write($"{x} "));
    }
}