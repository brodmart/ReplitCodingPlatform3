using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

class Program
{
    public class Etudiant
    {
        public string Nom { get; set; }
        public int Retards { get; set; }
        public int Points { get; set; }
        public int DetentionsPrises { get; set; }
        public bool BesoinDetention => Points >= 100;

        public Etudiant(string nom, int retards = 0, int points = 0, int detentionsPrises = 0)
        {
            Nom = nom;
            Retards = retards;
            Points = points;
            DetentionsPrises = detentionsPrises;
        }
    }

    static List<Etudiant> Etudiants = new List<Etudiant>
    {
        new Etudiant("Abdirahman"),
        new Etudiant("Alexander"),
        new Etudiant("Alexandre"),
        new Etudiant("Ali"),
        new Etudiant("Ben"),
        new Etudiant("Deshi"),
        new Etudiant("Fidel"),
        new Etudiant("Haaroon"),
        new Etudiant("Jakub"),
        new Etudiant("Kadija"),
        new Etudiant("Karl-Hendz"),
        new Etudiant("Mohamed"),
        new Etudiant("Mohamed Houssam")
    };

    static async Task Main()
    {
        bool quitter = false;

        while (!quitter)
        {
            try
            {
                Console.Clear();
                AfficherEtudiants();
                Console.Out.Flush();

                Console.WriteLine();
                Console.WriteLine("Menu:");
                Console.WriteLine("1. Ajouter un retard pour un etudiant");
                Console.WriteLine("2. Verifier qui a besoin de detention");
                Console.WriteLine("3. Confirmer une detention prise");
                Console.WriteLine("4. Ajouter un nouvel etudiant");
                Console.WriteLine("5. Quitter");
                Console.Write("Votre choix: ");
                Console.Out.Flush();

                var choixStr = await ReadLineWithTimeoutAsync(10);
                if (string.IsNullOrEmpty(choixStr))
                {
                    Console.WriteLine("Temps d'attente dépassé. Veuillez réessayer.");
                    Console.Out.Flush();
                    continue;
                }

                if (int.TryParse(choixStr, out int choix))
                {
                    switch (choix)
                    {
                        case 1:
                            await AjouterRetard();
                            break;
                        case 2:
                            VerifierDetentions();
                            break;
                        case 3:
                            await ConfirmerDetention();
                            break;
                        case 4:
                            await AjouterNouvelEtudiant();
                            break;
                        case 5:
                            quitter = true;
                            break;
                        default:
                            Console.WriteLine("Choix invalide. Essayez encore.");
                            Console.Out.Flush();
                            break;
                    }
                }
                else
                {
                    Console.WriteLine("Veuillez entrer un numero valide.");
                    Console.Out.Flush();
                }

                if (!quitter)
                {
                    await Task.Delay(2000);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Une erreur s'est produite: {ex.Message}");
                Console.Out.Flush();
                await Task.Delay(2000);
            }
        }
    }

    static async Task<string> ReadLineWithTimeoutAsync(int timeoutSeconds)
    {
        using var cts = new CancellationTokenSource(timeoutSeconds * 1000);
        var tcs = new TaskCompletionSource<string>();

        var task = Task.Run(() =>
        {
            try
            {
                var input = Console.ReadLine();
                tcs.TrySetResult(input ?? string.Empty);
            }
            catch (Exception ex)
            {
                tcs.TrySetException(ex);
            }
        });

        try
        {
            using (cts.Token.Register(() => tcs.TrySetResult(string.Empty)))
            {
                return await tcs.Task;
            }
        }
        catch (OperationCanceledException)
        {
            return string.Empty;
        }
    }

    static void AfficherEtudiants()
    {
        Etudiants = Etudiants.OrderBy(e => e.Nom).ToList();
        Console.WriteLine("\nEtudiants et Points:");
        Console.WriteLine("-----------------------");
        Console.WriteLine($"{"Nom",-15} {"Retards",-15} {"Points",-10} {"Detentions Prises",-15}");
        Console.WriteLine(new string('-', 55));
        Console.Out.Flush();

        foreach (var etudiant in Etudiants)
        {
            Console.WriteLine($"{etudiant.Nom,-15} {etudiant.Retards,-15} {etudiant.Points,-10} {etudiant.DetentionsPrises,-15}");
            Console.Out.Flush();
        }
    }

    static async Task AjouterRetard()
    {
        Console.Write("Entrez le nom de l'etudiant: ");
        Console.Out.Flush();
        string nom = await ReadLineWithTimeoutAsync(10);
        if (string.IsNullOrEmpty(nom))
        {
            Console.WriteLine("Temps d'attente dépassé.");
            Console.Out.Flush();
            return;
        }

        var etudiant = Etudiants.FirstOrDefault(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase));
        if (etudiant != null)
        {
            Console.Write("Entrez le nombre de minutes de retard: ");
            Console.Out.Flush();
            var minutesStr = await ReadLineWithTimeoutAsync(10);
            if (string.IsNullOrEmpty(minutesStr))
            {
                Console.WriteLine("Temps d'attente dépassé.");
                Console.Out.Flush();
                return;
            }

            if (int.TryParse(minutesStr, out int minutesRetard))
            {
                int points = CalculerPoints(minutesRetard);
                etudiant.Retards++;
                etudiant.Points += points;

                Console.WriteLine($"{etudiant.Nom} a ete en retard de {minutesRetard} minutes. {points} points ajoutes.");
                Console.WriteLine("Impression du billet de retard...");
                Console.Out.Flush();
            }
            else
            {
                Console.WriteLine("Entree invalide pour les minutes. Essayez encore.");
                Console.Out.Flush();
            }
        }
        else
        {
            Console.WriteLine("Etudiant non trouve.");
            Console.Out.Flush();
        }
    }

    static void VerifierDetentions()
    {
        Console.WriteLine("\nEtudiants ayant besoin de detention:");
        Console.WriteLine("-------------------------------------");
        Console.WriteLine($"{"Nom",-15} {"Points",-10} {"Detentions Prises",-15}");
        Console.WriteLine(new string('-', 40));
        Console.Out.Flush();

        var besoinDetention = Etudiants.Where(e => e.BesoinDetention);
        if (!besoinDetention.Any())
        {
            Console.WriteLine("Aucun.");
        }
        else
        {
            foreach (var etudiant in besoinDetention)
            {
                Console.WriteLine($"{etudiant.Nom,-15} {etudiant.Points,-10} {etudiant.DetentionsPrises,-15}");
            }
        }
        Console.Out.Flush();
    }

    static async Task ConfirmerDetention()
    {
        Console.Write("Entrez le nom de l'etudiant: ");
        Console.Out.Flush();
        string nom = await ReadLineWithTimeoutAsync(10);
        if (string.IsNullOrEmpty(nom))
        {
            Console.WriteLine("Temps d'attente dépassé.");
            Console.Out.Flush();
            return;
        }

        var etudiant = Etudiants.FirstOrDefault(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase));
        if (etudiant != null && etudiant.BesoinDetention)
        {
            etudiant.Points -= 100;
            etudiant.DetentionsPrises++;
            Console.WriteLine($"Detention confirmee pour {etudiant.Nom}. 100 points retires.");
        }
        else if (etudiant != null)
        {
            Console.WriteLine($"{etudiant.Nom} n'a pas besoin de detention.");
        }
        else
        {
            Console.WriteLine("Etudiant non trouve.");
        }
        Console.Out.Flush();
    }

    static async Task AjouterNouvelEtudiant()
    {
        Console.Write("Entrez le nom du nouvel etudiant: ");
        Console.Out.Flush();
        string nom = await ReadLineWithTimeoutAsync(10);
        if (string.IsNullOrEmpty(nom))
        {
            Console.WriteLine("Temps d'attente dépassé.");
            Console.Out.Flush();
            return;
        }

        if (Etudiants.Any(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase)))
        {
            Console.WriteLine("L'etudiant existe deja.");
        }
        else
        {
            Etudiants.Add(new Etudiant(nom));
            Etudiants = Etudiants.OrderBy(e => e.Nom).ToList();
            Console.WriteLine($"Etudiant {nom} ajoute et trie.");
        }
        Console.Out.Flush();
    }

    static int CalculerPoints(int minutesRetard)
    {
        if (minutesRetard <= 1)
            return 0;
        else if (minutesRetard <= 7)
            return (minutesRetard - 1) * 1;
        else if (minutesRetard <= 27)
            return (minutesRetard - 7) * 2 + 6;
        else if (minutesRetard <= 45)
            return (minutesRetard - 27) * 3 + 46;
        else
            return 100;
    }
}