---
name: meta-ads-specialist
description: Dodawaj i stosuj osobiste wytyczne oraz dobre praktyki specjalisty, niezależne od wspólnej wiedzy narzędzia i kontekstu klientów. Użyj przy prośbie o własną metodę pracy, aktualizację wytycznej lub przygotowaniu analizy z profilem operatora.
---

# Osobista warstwa specjalisty

Przeczytaj [proces profilu](../../docs/specialist-guidance.md). Na początku analizy, planowania kampanii i rekomendacji wykonaj `python3 workbench.py specialist list`. Brak profilu nie blokuje pracy. Dobierz aktywne wytyczne po temacie i odczytaj potrzebne treści przez `specialist read`. Nie wczytuj wszystkich dokumentów ani innych profili.

Profil jest osobistą, ogólną metodą pracy. Dane kont, cele klienta, brandbooki, warunki oferty, przykłady zawierające dane klientów i notatki ze spotkań należą do `context/` danego klienta. Nie eksportuj ich do profilu nawet wtedy, gdy specjalista obsługuje oba konta. Jeżeli użytkownik chce zapisać doświadczenie, opracuj z nim samą zasadę bez danych pozwalających odtworzyć klienta. Jeśli przypisanie materiału do warstwy jest niejasne, ustal zakres przed dodaniem.

Nową wytyczną przygotuj jako Markdown w `specialist/inbox/` lub przyjmij wskazany plik TXT/MD. Zapisz sens metody, kiedy ją stosować, wyjątki i podstawę, o ile są znane. Nie wymuszaj uzupełnienia całego szablonu. Użyj `specialist add`; komenda tworzy propozycję. Gdy użytkownik poleca stosowanie własnej wytycznej, zapisz `specialist status --status active` z rzeczywistym uzasadnieniem. Nie pytaj ponownie o tę samą jednoznaczną dyspozycję.

Poprawkę zapisz przez `specialist add --id ...`. Nowa wersja pozostaje robocza do aktywacji, a dotychczasowa jest nadal dostępna. Aktywacja nowej wersji zachowuje historię poprzedniej. Nie edytuj materiałów rejestru ręcznie i nie poprawiaj cudzych wytycznych pod cudzym profilem. Podłączenie innego specjalisty przez `specialist attach` jest jawną zmianą operatora, nie sposobem wyszukania wygodniejszej zasady.

Kolejność stosowania:

1. Zakaz kasowania i wymóg akceptacji konkretnego planu zmian w Meta obowiązują niezależnie od profilu.
2. Uwzględnij bieżącą dyspozycję operatora oraz potwierdzone cele i ograniczenia klienta.
3. W zakresie metod pracy stosuj pasujące aktywne wytyczne specjalisty przed domyślnymi metodami ze wspólnej bazy.
4. Pozostałe decyzje oprzyj na wspólnych skillach i kompendium.

Własna metoda nie zmienia faktów z danych ani możliwości API. Gdy wytyczna koliduje z ograniczeniem klienta lub opiera się na nieaktualnym założeniu, pokaż konkretną rozbieżność i jej wpływ na decyzję. Nie ogłaszaj sprzeczności tylko dlatego, że specjalista ma inną preferowaną metodę niż domyślna.

Przy rekomendacji zapisz w notatce analitycznej profil, ID i rewizję wykorzystanej wytycznej, SHA-256, jej odczytaną treść oraz opis zastosowania. Te odwołania są osobne od `context_basis`, które wskazuje ustalenia klienta. W tekście raportu przedstaw wniosek i uzasadnienie, bez wewnętrznych oznaczeń. Redakcję wykonaj przez miodkuj zgodnie z AGENTS.md.
