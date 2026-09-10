---
name: meta-ads-audit
description: Wykonaj audyt jednego lub kilku kont Meta Ads w FB Manager, przedstaw obserwacje, hipotezy i rekomendacje powiązane z danymi. Używaj dla audytów, diagnozy i próśb o optymalizację bez wykonywania zmian. Zakres audytu zależy od dostępnych danych; źródła Meta i demo nie zapewniają jeszcze pełnej diagnostyki konta.
---

# Audyt konta

Pracuj z katalogu projektu, dwa poziomy powyżej tego pliku. Użyj lokalnego `.venv/bin/meta-ads` albo zainstalowanego `meta-ads`. [AGENTS.md](../../AGENTS.md) określa wybór kont, dat i źródła. Najpierw odczytaj `capabilities`; prawdziwego konta nie zastępuj kontem demo.

## Podstawa analizy

Stosuj [standard rekomendacji](../../docs/analysis-standard.md). Głównym wynikiem audytu są konkretne działania, testy i pomysły na poprawę wyniku biznesowego. Zacznij od priorytetów i uzasadnij je danymi. ID oraz treść wewnętrznych wytycznych zachowaj w notatce; nie przytaczaj ich w raporcie. Istotne braki powiąż z konkretną decyzją i kontrolą, bez powtarzania ogólnych zastrzeżeń.

Przeczytaj [indeks kompendium](../../knowledge/meta-ads/README.md), następnie wybierz odpowiednie karty z [zasad analizy](../../knowledge/meta-ads/analysis-rules.md). DQ-01–03 służą ocenie podstaw wnioskowania; pozostałe dobierz do pytania i dostępnych danych. Definicje oraz ograniczenia wzorów znajdują się w [metrykach i metodach](../../knowledge/meta-ads/metrics-and-methods.md).

Stosuj tylko reguły pasujące do celu i warunków. Materiały mają status roboczych wytycznych przed recenzją specjalistów. Nie przedstawiaj hipotezy jako potwierdzonej przyczyny ani reguły wymagającej brakujących odczytów jako wykonanej kontroli. Rekomendacja silnika również wymaga sprawdzenia warunków; np. brak lokalnego mapowania celu nie oznacza błędnej kampanii.

W osobnej notatce analitycznej zapisz wersję kompendium, ID/wersje reguł, źródła, zakres i snapshot, obserwacje, braki danych oraz uzasadnienie działania lub jego braku. Nie zmieniaj oryginalnego JSON raportu. Liczby wylicza Python; jeśli potrzebna metoda nie jest jeszcze dostępna w CLI, nie wymyślaj wyniku ani nie deklaruj wykonania takiej komendy. Możesz wskazać potrzebne obliczenie lub wykonać jawne, odtwarzalne obliczenie lokalne na dostępnych danych.

## Przepływ

1. Ustal wszystkie żądane pary klient–konto na podstawie katalogu. Nie zawężaj audytu konta do jednej kampanii lub jednego celu. Dla wielu kont zachowaj osobne źródła i wyniki.
2. Gdy nie wskazano okresu, przyjmij ostatnie 30 pełnych dni i podaj to założenie. W demo użyj 30 dni kończących się na końcu dostępnego zestawu i oznacz daty jako demonstracyjne.
3. Wykonaj `sync` dla wymaganego okresu, sprawdź wynik, a następnie `audit` z tym samym okresem i `--snapshot` zwróconym przez synchronizację.
4. Przeczytaj `coverage`, wyniki kampanii i grup celów, `recommendations` oraz `limitations`. `status: PARTIAL` oznacza audyt częściowy, nawet jeśli komenda zakończyła się poprawnie. Obszar `unavailable` nie przeszedł kontroli.
5. Uwzględnij odrzucenia, odłożone pomysły i trwające testy z `recommendation_history`. Nowe kompletne propozycje zapisuj według meta-ads-decisions. Przedstaw priorytety zmian i testów, następnie dane uzasadniające każdą rekomendację oraz sposób oceny rezultatu. Rekomendacje silnika są materiałem do interpretacji. Pomysły agenta oprzyj na konkretnych danych lub pasujących wytycznych i przedstaw jako propozycje testów. Wskaż tylko te braki, które wpływają na decyzję.

Przykład operacyjny:

```bash
meta-ads --demo sync --client demo-leads --account act_DEMO_LEADS --last-days 30
meta-ads --demo audit --client demo-leads --account act_DEMO_LEADS --last-days 30 --snapshot SYNC_ID
```

`SYNC_ID` pochodzi z pierwszej odpowiedzi. Obie komendy wykonujesz samodzielnie, bez proszenia użytkownika o uruchamianie skryptów. Przedstawienie rekomendacji nie oznacza wykonania zmian kampanii.

## Ocena

- Leady: rozróżnij koszt leada, jego kwalifikację i sprzedaż. Bez CRM nie oceniaj jakości leadów. E-commerce: ROAS raportowany nie dowodzi rentowności; do tego potrzebne są marża i zwroty.
- Przekroczenie zapisanego CPL/CPA/ROAS to obserwacja, nie dowód przyczyny. Przed sugerowaniem konkretnej zmiany budżetu potrzebne są m.in. skala danych, historia zmian, pomiar i aktualne ustawienia.
- Dostępne dane nie zawierają obecnie targetowania, kreacji, budżetów, konfiguracji pomiaru ani historii zmian. Nie wystawiaj tym obszarom pozytywnej oceny i nie wymyślaj zaleceń dotyczących nieodczytanych ustawień.
- Przy zerowych lub brakujących konwersjach rozróżnij brak wyniku od braku pomiaru. Wskazanie kontroli pomiaru nie oznacza stwierdzenia awarii.
- Każda rekomendacja zawiera: obserwację, kampanię/konto, konkretne dane i okres, proponowane działanie, czego jeszcze trzeba się dowiedzieć i jak ocenić rezultat. Nie wymuszaj rekomendacji zmiany, gdy dane jej nie uzasadniają.
- Audyt kilku kont pokazuj z osobnymi sekcjami lub w tabeli. Oddziel braki dostępu od wyników biznesowych. Nie twórz jednego rankingu dla nieporównywalnych celów.

Na końcu wskaż najbliższe działania w kolejności. Nie pytaj o zgodę na każdą kolejną analizę mieszczącą się w prośbie o audyt; uzyskane w rozmowie upoważnienia zachowują ważność w swoim zakresie.

## Podłączone konto Meta

Wykonuj komendy bez `--demo`. `audit` działa na zapisanym snapshotcie i nie pobiera dodatkowych ustawień konta. Przed analizą odczytaj cele i historię rekomendacji przez [meta-ads-decisions](../meta-ads-decisions/SKILL.md). Wersjonowane mapowanie i obliczenia są w `goal_measurements`, a `business_goal_status` opisuje kompletność przypisania. `objective` i typy `reported_actions` są danymi pomocniczymi. Nie sumuj nakładających się zdarzeń i nie obliczaj z nich arbitralnie CPL/CPA/ROAS. Brak celu w lokalnym profilu nie oznacza złej konfiguracji kampanii Meta.

Jeśli okres nie zawiera wydatków, wskaż brak podstaw do oceny skuteczności. Możesz zaproponować okres z emisją. Brak emisji przy kampaniach wstrzymanych nie jest sam w sobie awarią.

## Redakcja przed przekazaniem

Każdą analizę, audyt, rekomendacje i ich podsumowanie poddaj redakcji [miodkuj](../miodkuj/SKILL.md) w trybie Embedded or file mode. Zastosuj [zasady projektu](../../AGENTS.md#redakcja-raportów-po-polsku), w tym końcową kontrolę `references/eval.md` i zapis kontroli dla raportu w pliku. Zachowaj dowody, braki danych oraz rozróżnienie obserwacji, hipotezy i rekomendacji. Prośba o audyt konta nie przełącza miodkuj w tryb audytu językowego.

## Eksport do PDF

Jeżeli użytkownik chce dokument, wykonaj [meta-ads-pdf](../meta-ads-pdf/SKILL.md) na zapisanym raporcie. Komentarz agenta można dołączyć jako osobny `pdf_notes`; nie zmieniaj źródłowych obliczeń.

Przy raporcie HTML stosuj układ z AGENTS.md: w katalogu raportu tylko `raport.html` i `materialy/`. Wszystkie pliki pomocnicze, w tym JSON, grafiki, notatki i kontrola językowa, trafiają do `materialy/`. Jeśli PDF towarzyszy temu HTML, także zapisz go w `materialy/` i podaj bezpośredni link do PDF. Sprawdź względne odnośniki po wygenerowaniu.
