namespace AdvancedProgram
{
    public class Program 
    {
        static async Task Main(string[] args)
        {
            Console.WriteLine("Starting large code test...");

            // Generate and process large amounts of data
            var numbers = Enumerable.Range(1, 100000).ToList();
            var processedData = await ProcessDataAsync(numbers);

            Console.WriteLine($"Processed {processedData.Count} items");
            PrintSummary(processedData);
        }

        private static async Task<List<int>> ProcessDataAsync(List<int> data)
        {
            var tasks = new List<Task<int>>();
            foreach (var item in data)
            {
                tasks.Add(ProcessItemAsync(item));
            }
            return (await Task.WhenAll(tasks)).ToList();
        }

        private static async Task<int> ProcessItemAsync(int item)
        {
            await Task.Delay(1); // Simulate some async work
            return checked(item * 2); // Add checked arithmetic
        }

        private static void PrintSummary(List<int> data)
        {
            // Convert to long before summing to prevent overflow
            var sum = data.Select(x => (long)x).Sum();
            var avg = data.Average();
            var max = data.Max();
            var min = data.Min();

            Console.WriteLine($"Summary Statistics:");
            Console.WriteLine($"Sum: {sum:N0}");
            Console.WriteLine($"Average: {avg:N2}");
            Console.WriteLine($"Maximum: {max:N0}");
            Console.WriteLine($"Minimum: {min:N0}");

            // Group analysis - also convert to long for sums
            var groups = data
                .GroupBy(x => x % 10)
                .OrderBy(g => g.Key)
                .Select(g => new { 
                    Remainder = g.Key,
                    Count = g.Count(),
                    Average = g.Average(),
                    Sum = g.Select(x => (long)x).Sum()
                })
                .ToList();

            Console.WriteLine("\nGroup Analysis:");
            foreach (var group in groups)
            {
                Console.WriteLine($"Remainder {group.Remainder}: Count={group.Count}, Avg={group.Average:N2}, Sum={group.Sum:N0}");
            }
        }
    }

    // Rest of the classes remain unchanged
    public class DataProcessor
    {
        public static double CalculateComplexMetric(IEnumerable<int> data)
        {
            return data
                .Where(x => x > 0)
                .Select(x => Math.Pow(x, 2))
                .Average();
        }

        public static Dictionary<int, double> GenerateStatistics(IEnumerable<int> data)
        {
            return data
                .GroupBy(x => x % 5)
                .ToDictionary(
                    g => g.Key,
                    g => g.Select(x => Math.Pow(x, 2)).Average()
                );
        }
    }

    public class MetricsCalculator
    {
        public static class Statistics
        {
            public static double CalculateVariance(IEnumerable<int> values)
            {
                var avg = values.Average();
                return values.Select(v => Math.Pow(v - avg, 2)).Average();
            }

            public static double CalculateStandardDeviation(IEnumerable<int> values)
            {
                return Math.Sqrt(CalculateVariance(values));
            }

            public static double CalculateMedian(IEnumerable<int> values)
            {
                var sorted = values.OrderBy(v => v).ToList();
                int mid = sorted.Count / 2;
                return sorted.Count % 2 == 0
                    ? (sorted[mid - 1] + sorted[mid]) / 2.0
                    : sorted[mid];
            }
        }
    }
}