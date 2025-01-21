using System;
using System.Collections.Generic;
using System.Linq;

class Program
{
    public class Etudiant
    {
        public string Nom { get; set; }
        public int Retards { get; set; }
        public int Points { get; set; }
        public int DetentionsPrises { get; set; }
        public bool BesoinDetention => Points >= 100;

        public Etudiant(string nom)
        {
            Nom = nom;
            Retards = 0;
            Points = 0;
            DetentionsPrises = 0;
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

    static void Main(string[] args)
    {
        bool quitter = false;

        while (!quitter)
        {
            AfficherEtudiants();
            AfficherMenu();

            string input = Console.ReadLine();
            if (int.TryParse(input, out int choix))
            {
                switch (choix)
                {
                    case 1:
                        AjouterRetard();
                        break;
                    case 2:
                        VerifierDetentions();
                        break;
                    case 3:
                        ConfirmerDetention();
                        break;
                    case 4:
                        AjouterNouvelEtudiant();
                        break;
                    case 5:
                        quitter = true;
                        break;
                    default:
                        Console.WriteLine("Choix invalide. Essayez encore.");
                        break;
                }
            }
            else
            {
                Console.WriteLine("Veuillez entrer un numero valide.");
            }
        }
    }

    static void AfficherMenu()
    {
        Console.WriteLine("\nMenu:");
        Console.WriteLine("1. Ajouter un retard pour un etudiant");
        Console.WriteLine("2. Verifier qui a besoin de detention");
        Console.WriteLine("3. Confirmer une detention prise");
        Console.WriteLine("4. Ajouter un nouvel etudiant");
        Console.WriteLine("5. Quitter");
        Console.Write("Votre choix: ");
    }

    static void AfficherEtudiants()
    {
        Console.WriteLine("\nEtudiants et Points:");
        Console.WriteLine("-----------------------");
        Console.WriteLine($"{"Nom",-15} {"Retards",-15} {"Points",-10} {"Detentions Prises",-15}");
        Console.WriteLine(new string('-', 55));

        foreach (var etudiant in Etudiants.OrderBy(e => e.Nom))
        {
            Console.WriteLine($"{etudiant.Nom,-15} {etudiant.Retards,-15} {etudiant.Points,-10} {etudiant.DetentionsPrises,-15}");
        }
    }

    static void AjouterRetard()
    {
        Console.Write("\nEntrez le nom de l'etudiant: ");
        string nom = Console.ReadLine();
        var etudiant = Etudiants.FirstOrDefault(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase));

        if (etudiant != null)
        {
            Console.Write("Entrez le nombre de minutes de retard: ");
            if (int.TryParse(Console.ReadLine(), out int minutesRetard))
            {
                int points = CalculerPoints(minutesRetard);
                etudiant.Retards++;
                etudiant.Points += points;
                Console.WriteLine($"\n{etudiant.Nom} a ete en retard de {minutesRetard} minutes. {points} points ajoutes.");
            }
            else
            {
                Console.WriteLine("\nEntree invalide pour les minutes.");
            }
        }
        else
        {
            Console.WriteLine("\nEtudiant non trouve.");
        }
    }

    static void VerifierDetentions()
    {
        var besoinDetention = Etudiants.Where(e => e.BesoinDetention);

        Console.WriteLine("\nEtudiants ayant besoin de detention:");
        Console.WriteLine("-------------------------------------");

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
    }

    static void ConfirmerDetention()
    {
        Console.Write("\nEntrez le nom de l'etudiant: ");
        string nom = Console.ReadLine();
        var etudiant = Etudiants.FirstOrDefault(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase));

        if (etudiant != null)
        {
            if (etudiant.BesoinDetention)
            {
                etudiant.Points -= 100;
                etudiant.DetentionsPrises++;
                Console.WriteLine($"\nDetention confirmee pour {etudiant.Nom}. 100 points retires.");
            }
            else
            {
                Console.WriteLine($"\n{etudiant.Nom} n'a pas besoin de detention.");
            }
        }
        else
        {
            Console.WriteLine("\nEtudiant non trouve.");
        }
    }

    static void AjouterNouvelEtudiant()
    {
        Console.Write("\nEntrez le nom du nouvel etudiant: ");
        string nom = Console.ReadLine();

        if (string.IsNullOrWhiteSpace(nom))
        {
            Console.WriteLine("\nLe nom ne peut pas être vide.");
            return;
        }

        if (Etudiants.Any(e => e.Nom.Equals(nom, StringComparison.OrdinalIgnoreCase)))
        {
            Console.WriteLine("\nL'etudiant existe deja.");
        }
        else
        {
            Etudiants.Add(new Etudiant(nom));
            Console.WriteLine($"\nEtudiant {nom} ajoute.");
        }
    }

    static int CalculerPoints(int minutesRetard)
    {
        if (minutesRetard <= 1)
            return 0;
        if (minutesRetard <= 7)
            return (minutesRetard - 1) * 1;
        if (minutesRetard <= 27)
            return (minutesRetard - 7) * 2 + 6;
        if (minutesRetard <= 45)
            return (minutesRetard - 27) * 3 + 46;
        return 100;
    }
}