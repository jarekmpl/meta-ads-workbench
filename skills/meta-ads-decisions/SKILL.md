---
name: meta-ads-decisions
description: Zapisuj i odczytuj cele biznesowe kampanii Meta Ads, definicje wyników, progi kosztowe oraz historię rekomendacji i testów. Używaj przy ustalaniu celu, decyzjach operatora, rozpoczęciu lub ocenie testu oraz przed kolejnym audytem, aby uwzględnić wcześniejsze ustalenia. Wszystkie zapisy są lokalne.
---

# Cele i decyzje

Przeczytaj [proces i kontrakty](../../docs/goals-and-recommendations.md). Pracuj w zakresie klienta z AGENTS.md i workspace.json. W przestrzeni instalowanej używaj `python3 workbench.py meta`; w katalogu rozwojowym `.venv/bin/meta-ads`. Sprawdź capabilities. Nie zastępuj danych Meta demonstracją.

## Przed analizą

1. Odczytaj `goals list`, `recommendations list` i aktualny kontekst klienta. Sprawdź daty obowiązywania, przypisania kampanii i terminy spraw. Zapoznaj się również z odrzuconymi pomysłami.
2. Użyj istniejących definicji. Nowy cel ustalaj na podstawie wypowiedzi operatora, kontekstu i zdarzeń zapisanych w snapshotcie. Zapytaj tylko o brakujące decyzje: co jest wynikiem, gdzie powstaje, jaki jest próg i od kiedy obowiązuje przypisanie. Nie zgaduj po samej nazwie lub objective.
3. Dobierz dokładny `action_type`, a dla ROAS także odpowiadający mu klucz wartości zakupu. Nie sumuj aliasów. Kliknięcie do sprzedawcy biletów jest `proxy`, jeśli nie mierzymy sprzedaży. Nie zastępuj tego zdarzenia ogólnym kliknięciem reklamy. Użycie brakującego klucza nie wdraża śledzenia.
4. Domyślnie zachowaj `missing_action_policy: unknown`. `zero_when_omitted` wymaga potwierdzonej interpretacji pomiaru, zapisanej z autorem i odwołaniem. Nie wymyślaj potwierdzenia ani progu na podstawie wyniku, który chcesz uzyskać.
5. Pliki przygotuj lokalnie według schematów i przykładów. Zapisz cel przez `goals set`, a następnie konkretne przypisania przez `goals assign`. Nowa wersja celu wymaga osobnych przypisań; nie zmienia automatycznie kampanii. Przeczytaj odpowiedź i sprawdź zapisane ID oraz wersje.

## Po analizie i przy decyzji

Zapisuj uzasadnione, konkretne propozycje przez `recommendations add`. Przed zapisem porównaj je z historią, także semantycznie. Plan oceny powinien wskazywać hipotezę, kampanie, równy okres bazowy i obserwacji, wskaźnik, próg sukcesu lub poprawę względem bazy, ewentualne minimum wyników i warunek przerwania. Parametry zaproponowane przez agenta przedstaw jako propozycję. Brak danych koniecznych do kompletnego planu uzupełnij pytaniem; nie twórz pozornego testu z losowymi datami.

Zapisz decyzję przez `recommendations event`, korzystając z aktualnej wersji. Autor i evidence_refs muszą wskazywać rzeczywiste ustalenie. Ogólne „działaj” nie rozstrzyga kilku różnych propozycji. Przy niejasności ustal konkretny zakres. Rejestracja akceptacji pomysłu nie oznacza akceptacji planu zmian na Meta. `start` zapisuj po potwierdzeniu rzeczywistej daty wdrożenia. Agent nie może sam zadeklarować, że operator wdrożył zmianę.

Odrzucenie zachowaj wraz z przyczyną, odłożenie z datą powrotu. Powrót do wcześniejszego pomysłu to nowy wpis z `followup_of` i konkretnym nowym uzasadnieniem w `followup_reason`. Poprzedniego wpisu nie nadpisuj. `cancel` kończy lokalną obserwację, nie zatrzymuje kampanii.

## Kolejna ocena

Odczytaj `recommendations list --due`. Pobierz snapshot obejmujący oba pełne okresy i wykonaj `recommendations evaluate` z ID oraz oczekiwaną wersją. Gdy zmieniło się przypisanie, nie obchodź blokady. Wyjaśnij, jaki nowy zakres lub plan trzeba ustalić. Do porównania realizacji celu użyj `analyze --goal ...`; domyślnie porównuje dwa okresy po 7 pełnych dni, a jawne daty wskazują okres bieżący.

Wyniki i zmiany procentowe bierz z JSON. Brak rozstrzygnięcia nie jest porażką testu. Spełnienie kryterium opisuje wyniki z porównania; przed rekomendacją dalszego działania sprawdź inne zmiany i kontekst. Nie ogłaszaj zwycięzcy eksperymentu A/B na podstawie porównania przed i po.

W raporcie Meta korzystaj z `goal_measurements`, `business_goal_status`, `comparisons` i `recommendation_history`. Zapisany raport odtwarzaj przez `report show`; nowy odczyt rejestru może zawierać późniejsze decyzje. Nowy rejestr nie jest harmonogramem. Odczyt terminów wykonujesz podczas pracy; nie obiecuj samoczynnego powiadomienia bez osobnego mechanizmu.

Rekomendacje i komentarze opracuj według [standardu analiz](../../docs/analysis-standard.md) i [miodkuj](../miodkuj/SKILL.md), wraz z jego kontrolą końcową. Konto pozostaje objęte zakazem kasowania i wymogiem akceptacji każdego konkretnego planu zmian. Komendy rejestru i analiz nie zmieniają Meta. Osobny kreator może tworzyć nowe obiekty PAUSED wyłącznie po akceptacji konkretnego planu; akceptacja rekomendacji w tym rejestrze nie jest taką zgodą.
