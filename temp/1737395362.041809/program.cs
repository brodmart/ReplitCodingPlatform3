using System;
using System.Collections.Generic;

class User
{
    public string Name { get; set; }
    public string Role { get; set; } // "Tutor" or "Student"
    public string Subject { get; set; }
}

class Session
{
    public string Student { get; set; }
    public string Tutor { get; set; }
    public string Subject { get; set; }
    public DateTime Date { get; set; }
}

class TutoringPlatform
{
    private List<User> users = new List<User>();
    private List<Session> sessions = new List<Session>();

    public void RegisterUser()
    {
        Console.WriteLine("Inscription utilisateur");
        Console.Write("Nom : ");
        string name = Console.ReadLine();
        Console.Write("Rôle (Tutor/Student) : ");
        string role = Console.ReadLine();
        Console.Write("Sujet (Math/Science/etc.) : ");
        string subject = Console.ReadLine();

        users.Add(new User { Name = name, Role = role, Subject = subject });
        Console.WriteLine($"Utilisateur {name} inscrit avec succès !");
    }

    public void MatchStudentWithTutor()
    {
        Console.WriteLine("Jumelage étudiant-tuteur");
        Console.Write("Nom de l'étudiant : ");
        string studentName = Console.ReadLine();

        User student = users.Find(u => u.Name == studentName && u.Role == "Student");
        if (student == null)
        {
            Console.WriteLine("Étudiant non trouvé !");
            return;
        }

        User tutor = users.Find(u => u.Role == "Tutor" && u.Subject == student.Subject);
        if (tutor == null)
        {
            Console.WriteLine("Aucun tuteur disponible pour ce sujet.");
            return;
        }

        Console.WriteLine($"Tuteur trouvé : {tutor.Name} pour le sujet {student.Subject}");
        Console.Write("Entrez une date pour la session (AAAA-MM-JJ) : ");
        DateTime date = DateTime.Parse(Console.ReadLine());

        sessions.Add(new Session
        {
            Student = student.Name,
            Tutor = tutor.Name,
            Subject = student.Subject,
            Date = date
        });

        Console.WriteLine("Session programmée avec succès !");
    }

    public void ListSessions()
    {
        Console.WriteLine("Liste des sessions :");
        foreach (var session in sessions)
        {
            Console.WriteLine($"Étudiant : {session.Student}, Tuteur : {session.Tutor}, Sujet : {session.Subject}, Date : {session.Date.ToShortDateString()}");
        }
    }

    public void Run()
    {
        int choice;
        do
        {
            Console.WriteLine("\nPlateforme de tutorat :");
            Console.WriteLine("1. Inscrire un utilisateur");
            Console.WriteLine("2. Jumeler un étudiant avec un tuteur");
            Console.WriteLine("3. Afficher les sessions");
            Console.WriteLine("4. Quitter");
            Console.Write("Choix : ");
            choice = int.Parse(Console.ReadLine());

            switch (choice)
            {
                case 1:
                    RegisterUser();
                    break;
                case 2:
                    MatchStudentWithTutor();
                    break;
                case 3:
                    ListSessions();
                    break;
                case 4:
                    Console.WriteLine("Au revoir !");
                    break;
                default:
                    Console.WriteLine("Choix invalide.");
                    break;
            }
        } while (choice != 4);
    }
}

class Program
{
    static void Main()
    {
        TutoringPlatform platform = new TutoringPlatform();
        platform.Run();
    }
}