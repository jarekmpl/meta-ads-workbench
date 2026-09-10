# Plan wdrożenia v0.1

## Stan implementacji

Gotowe: konfiguracja Meta, lokalne wprowadzanie poświadczeń i potwierdzony test odczytu konta pilotażowego. Działa adapter listy kampanii i dziennych Insights z paginacją, uzgodnieniem sum konta, izolacją danych Meta/demo i raportowaniem offline. Szczegóły: [konfiguracja Meta](meta-setup.md).

Gotowy fundament demo: Python/CLI, modele JSON Schema, dwóch klientów, SQLite ze snapshotami, analizy tygodniowe, raporty i częściowy audyt. Skille raportowania i audytu obsługują też źródło Meta.

Etap 1 pozostaje otwarty w zakresie raportów asynchronicznych, wznawiania, porównania okresu z emisją z Ads Managerem i drugiego konta pilotażowego. Etap 2 wymaga mapowania celów/konwersji na rzeczywistych kontach. Pełny audyt i operacje zapisu pozostają do wdrożenia.

## Etap 1: fundament i odczyt

Zakres:

- Pakiet Python, konfiguracja środowiska, CLI i kontrakt błędów.
- Modele klienta, konta, celu, pieniędzy i zakresu operacji; migracje SQLite.
- Adapter danych przykładowych do pracy bez połączenia z Metą.
- Adapter Meta, jawne sesje, poświadczenia przez referencje i `auth check`.
- Pobieranie struktury i raportów, paginacja, raporty asynchroniczne i wznawianie synchronizacji.
- Zapis wersji danych i podstawowy raport kontrolny.

Odbiór:

- Dwa profile klientów nie mieszają danych ani sesji; próba użycia konta innego klienta jest blokowana przed API.
- Można pobrać strukturę i uzgodniony zakres danych jednego konta, a następnie dodać drugie bez zmiany kodu.
- Ponowna synchronizacja nie dubluje faktów; aktualizacje historii są widoczne w nowej wersji snapshotu.
- Wybrany raport jest porównany z Ads Managerem przy tych samych datach, strefie, atrybucji, poziomie i definicjach wyników. Rozbieżności są wyjaśnione, a tolerancja zaokrągleń jawna.
- Błąd dostępu, niepełna paginacja i ograniczenie API nie dają pozornie kompletnego raportu. Logi nie zawierają tokenów.

## Etap 2: analizy leadowe i sprzedażowe

Zakres: agregacja metryk, porównania okresów, kontrola wydatków względem planu, ranking obiektów w obrębie porównywalnego celu, analiza zmian składowych CPA/ROAS oraz pierwsze skille analityczne.

Odbiór:

- Na dwóch kontach pilotażowych powstają raporty dla lead generation i e-commerce.
- Każdy wniosek ilościowy ma źródło, definicję metryki i okres; obliczenia można odtworzyć z zapisanego snapshotu.
- System poprawnie rozpoznaje brak konwersji, brak danych, zerowy mianownik, niepełny dzień i niezgodne ustawienia raportów.
- Bez CRM/sklepu nie powstają twierdzenia o jakości leadów, marży lub rzeczywistej rentowności.
- Testy sprawdzają obliczenia wskaźników z agregatów oraz brak sumowania reach i dublowania konwersji.

## Etap 3: tworzenie i kontrolowane zmiany

Projekt procesu obejmuje [rozmowę, pozyskiwanie informacji i przygotowanie planu](campaign-planning-process.md) oraz [standard nazw](campaign-naming-standard.md). To specyfikacje do wdrożenia, nie dostępne komendy. Planowanie ma objąć także rejestracje i sprzedaż z pomiarem pomocniczym; pierwszy zakres wykonawcy pozostaje opisany poniżej.

Zakres: planowanie kampanii, walidacja zasobów, dziennik operacji, polityki, upoważnienia, utworzenie obiektów wstrzymanych, zmiany statusów i budżetów, odczyt kontrolny.

Pierwsze obsługiwane warianty: sprzedaż w witrynie z istniejącym źródłem zdarzeń oraz leady przez istniejący formularz Meta lub witrynę. Konkretne parametry i dostępność są sprawdzane dla wybranej wersji API i konta. MVP nie tworzy automatycznie nowych formularzy, katalogów ani niestandardowych grup odbiorców. Korzysta z dostarczonych materiałów reklamowych.

Odbiór:

- Z kompletnych briefów powstają dwa poprawne plany — leadowy i sprzedażowy.
- Brak strony, materiału, formularza lub źródła zdarzeń jest wykrywany przed wykonaniem zależnych operacji.
- Utworzone obiekty są wstrzymane, a ich identyfikatory i konfiguracja zweryfikowane przez API. Aktywacja wymaga odrębnego planu i upoważnienia.
- Nieaktualny plan, zmieniona treść, brak upoważnienia i przekroczenie polityki blokują wykonanie.
- Ponowne uruchomienie zakończonego planu nie tworzy duplikatów. Timeout zapisu, awaria w połowie i zmiana zewnętrzna są obsłużone z jawnym stanem wyniku.
- Testy integracyjne tworzą tylko jawnie wskazane obiekty wstrzymane na koncie pilotażowym. Test uruchomienia emisji jest osobnym, autoryzowanym działaniem.

Po etapach 1–3 otrzymujemy MVP: wspólny silnik, analizy obu typów i kontrolowane wykonywanie zmian.

## Etap 4: automatyzacja i ocena rezultatów

Zakres: harmonogram odczytów, analiz i propozycji, powiadomienia o istotnych zdarzeniach oraz ocena efektów. Samodzielne zmiany na kontach są zabronione. Każdy zapis wymaga akceptacji użytkownika dla konkretnego planu; kasowanie jest zabronione bezwarunkowo.

Odbiór:

- Przed zapisem działa tryb obserwacyjny: system rejestruje proponowane zmiany i uzasadnienia bez wykonywania ich w Mecie.
- Polityka określa konta, operacje, limity i warunki zatrzymania, ale nie zastępuje akceptacji konkretnego planu przez użytkownika. Kolejne małe zmiany nie obchodzą ani akceptacji, ani limitu łącznego.
- Niepełne dane, wygasły dostęp i nierozstrzygnięty wynik poprzedniego zapisu zatrzymują zależne zmiany.
- Raport efektów uwzględnia inne interwencje i nie przedstawia korelacji jako dowodu skuteczności.

## Późniejsze rozszerzenia

CRM i sklep, agregaty jakości leadów, marża/zwroty, analiza i generowanie materiałów, katalogi produktów, dodatkowe formaty kampanii, eksperymenty, adapter MCP, panel WWW i praca wielu operatorów.

## Kolejność najbliższych prac

1. Sprawdzić rzeczywisty raport za okres z emisją i porównać go z panelem Meta.
2. Uzgodnić i zapisać mapowanie zdarzeń oraz cele CPL/CPA/ROAS.
3. Podłączyć drugie konto pilotażowe i zweryfikować oba typy kampanii.
4. Dodać odczyt zestawów reklam, kreacji i konfiguracji pomiaru do pełniejszego audytu.
5. Rozszerzyć pobieranie o raporty asynchroniczne i wznawianie.

## Informacje potrzebne przed pilotem

- Dwa wskazane konta, ich właściciele i sposób udostępnienia aplikacji.
- Dostępność aplikacji Meta i osoba mogąca skonfigurować jej uprawnienia.
- Kampanie/projekty pilotażowe i definicje wyniku biznesowego.
- Docelowy CPL/CPA/ROAS i ograniczenia budżetowe, jeśli są już ustalone.
- Dostępne źródła zdarzeń, strony, formularze i materiały reklamowe.

Te informacje nie blokują tworzenia szkieletu, modeli i testów na danych przykładowych. Nie prosimy o wklejanie tokenów do rozmowy.
