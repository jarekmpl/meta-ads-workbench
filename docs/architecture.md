# Architektura v0.1

Działają adaptery demo i Meta w trybie odczytu, lokalne snapshoty, raporty i częściowy audyt. Wykonawca zmian pozostaje projektem. Moduły są na razie pojedynczymi plikami pakietu; poniższy podział na podpakiety jest strukturą docelową.

## Decyzje projektowe

Silnik wykonuje operacje deterministyczne: waliduje, pobiera, liczy, zapisuje i wykonuje plan. Agent LLM dobiera procedurę, interpretuje dowody, formułuje hipotezy i rozmawia z użytkownikiem. Obliczenia metryk i decyzja o dopuszczalności operacji należą do kodu.

W pierwszej wersji jeden proces CLI i lokalna baza SQLite wystarczą. Model uwzględnia wielu klientów od początku. Usługa sieciowa, kolejka zadań i osobna baza serwerowa będą potrzebne dopiero przy współdzielonej pracy lub większej skali.

Planowany podział pakietu:

```text
src/meta_ads_manager/
  cli/                # wejście, JSON na stdout, diagnostyka na stderr
  domain/             # modele, pieniądze, cele, plany i stany operacji
  providers/meta/     # SDK/API, uprawnienia, paginacja, wersja API
  storage/            # repozytoria, migracje, snapshoty, dziennik operacji
  ingestion/          # synchronizacja i normalizacja
  analytics/          # metryki, kontrola jakości, analizy
  planning/           # briefy, propozycje i wykonywalne plany
  execution/          # polityki, upoważnienia, wykonanie, odczyt kontrolny
  reporting/          # raporty JSON i Markdown
```

CLI i przyszły MCP wywołują te same usługi. Skille nie implementują własnych klientów HTTP ani obliczeń. Fundament używa Pydantic do kontraktów, standardowego `argparse` do CLI oraz pytest do testów. `argparse` pozwala utrzymać mały zestaw zależności i wspólny format błędów JSON. Wersje zależności są zapisane w `uv.lock`. Obecny adapter Meta używa standardowego `urllib` za własnym interfejsem GET. Parametry weryfikujemy z oficjalnym SDK Meta; nie jest ono zależnością wykonawczą.

## Połączenie z Metą

- Aplikacja Meta, konto reklamowe, przydziały zasobów i uprawnienia stanowią osobne elementy konfiguracji.
- Przed wyborem ścieżki autoryzacji trzeba sprawdzić sposób udostępnienia kont klientów. Token system user nie zastępuje automatycznie procesu logowania i zgody użytkownika aplikacji.
- `ads_read` i `ads_management` to podstawowe uprawnienia reklamowe; inne dobieramy do faktycznie używanych zasobów. Nie żądamy wszystkich uprawnień na zapas.
- Dla obsługi kont klientów należy sprawdzić wymagania Advanced Access, App Review i weryfikacji biznesowej dla konkretnej konfiguracji aplikacji.
- `auth check` sprawdza rzeczywisty dostęp do wskazanego konta i wymaganych zasobów. Sam ważny token nie oznacza gotowości do tworzenia reklam.
- Wersja Graph API jest jawna i przypięta. Adapter utrzymuje zestaw obsługiwanych celów, formatów i pól dla tej wersji. Nie obiecujemy pełnej zgodności z każdą funkcją interfejsu Ads Managera.
- Klient API obsługuje paginację, raporty asynchroniczne, timeouty, limity i ponawianie bezpiecznych odczytów. Przypadki niepewnego wyniku zapisu rozstrzyga dziennik operacji.

Sekrety są pobierane przez referencje do zmiennych środowiskowych lub magazynu poświadczeń. Nie występują w profilach, argumentach CLI, raportach ani logach. Redakcja obejmuje także URL-e paginacji, nagłówki i komunikaty błędów SDK. Każde konto używa jawnej sesji API; brak wspólnej globalnej sesji przełączanej między klientami.

Źródła referencyjne sprawdzone podczas przygotowania koncepcji 2026-09-09:

- [Oficjalne Python Business SDK](https://github.com/facebook/facebook-python-business-sdk) — obiekty reklamowe, sesje i operacje API.
- [Kolekcja Marketing API publikowana przez Metę](https://www.postman.com/meta/facebook-marketing-api/collection/0zr4mes/facebook-marketing-api-mapi) — rozpoczęcie integracji i poziomy dostępu.

Przed implementacją konkretnego endpointu należy sprawdzić jego aktualny kontrakt. Specyfikacja projektu nie zastępuje dokumentacji wybranej wersji API.

## Izolacja klientów

Każda operacja na koncie wymaga `client_id` i `account_id`. Kod sprawdza ich powiązanie przed wywołaniem API. Zapytania i klucze pamięci podręcznej zawierają zakres klienta oraz konta; przełączenie konta nie może odziedziczyć poprzednich poświadczeń.

Raporty są domyślnie ograniczone do jednego klienta. Porównanie między klientami wymaga osobnej, jawnej operacji. Taka operacja nie należy do MVP.

Lokalne rozdzielenie rekordów chroni przed pomyłkami aplikacji, ale nie jest izolacją bezpieczeństwa wobec użytkownika mającego pełny dostęp do tej samej bazy i sekretów. Instalacja współdzielona wymaga osobnego uwierzytelniania, autoryzacji i granic dostępu do magazynu danych.

## Wykonywanie zmian

Nadrzędne [zasady zmian na kontach](account-change-policy.md): bezwzględny zakaz kasowania i akceptacja użytkownika przed każdą zmianą. Poniższy wykonawca jest planowany, nie zaimplementowany.

Przepływ: propozycja → plan po walidacji → upoważnienie → wykonanie → odczyt kontrolny.

1. Propozycja określa konto, obiekty, bieżące wartości, żądane wartości, uzasadnienie i dowody.
2. Walidator pobiera świeży stan, sprawdza obsługiwane pola, zasoby, jednostki budżetu i politykę klienta. Brak wymaganych danych blokuje powstanie wykonywalnego planu.
3. System zapisuje niezmienny plan z czasem ważności i skrótem jego treści. Zmiana treści wymaga nowego planu i ponownego upoważnienia.
4. Upoważnienie wynika wyłącznie z wyraźnego zatwierdzenia konkretnego planu przez użytkownika. Polityka automatyzacji nie stanowi zgody na zapis. Samo `apply`, tekst w uzasadnieniu lub deklaracja agenta nie stanowią upoważnienia.
5. Przed zapisem wykonawca sprawdza ponownie politykę, ważność planu, zakres upoważnienia i bieżące wartości pól objętych zmianą. Rozbieżność daje `STATE_CONFLICT`.
6. Operacje mają trwałe identyfikatory i dziennik. Blokada konta serializuje lokalne wykonania. Zewnętrzne zmiany w Ads Managerze nadal mogą wystąpić między odczytem a zapisem; API nie traktujemy jako transakcyjnego magazynu z atomową blokadą.
7. Po zapisie wykonawca odczytuje stan z API i porównuje z oczekiwanym. Weryfikacja ustawień nie oznacza zatwierdzenia reklamy ani rozpoczęcia emisji.

Ponowne wykonanie zakończonego planu zwraca zapisany rezultat. Przy timeoutach zapisu stan przechodzi do `UNKNOWN`: najpierw uzgodnienie stanu z API, potem ewentualne dalsze działania. Nie ponawiamy w ciemno tworzenia kampanii. Jeśli nie da się jednoznacznie rozstrzygnąć rezultatu, operacja wymaga interwencji.

Plan tworzenia kampanii jest grafem zależności: kampania, zestawy reklam, materiały/kreacje i reklamy. Nowe obiekty mają domyślnie stan wstrzymany. Awaria w połowie zapisuje utworzone identyfikatory i wynik `PARTIAL`; nie uruchamia pozostałych obiektów. Aktywacja to osobny plan wymagający akceptacji użytkownika. Nie usuwa się utworzonych obiektów po błędzie; naprawa lub cofnięcie ustawień wymaga zaakceptowanego planu. Nie obiecujemy pełnego rollbacku: cofnięcie części ustawień może być możliwe, ale wydatków i historii emisji nie można cofnąć.

## Tryby pracy

| Tryb | Zakres |
| --- | --- |
| `analyst` | Odczyt, obliczenia, raporty i propozycje |
| `operator` | Wykonanie konkretnego upoważnionego planu |
| `autopilot` | Wyłącznie odczyty, analizy i lokalne propozycje; samodzielny zapis zabroniony |

Polityka określa konta, rodzaje zmian, limity bezwzględne i procentowe, łączny limit zmian w okresie oraz minimalny odstęp między nimi. Sprawdza też nadrzędny poziom budżetu: kampania lub zestaw reklam. Blokady analityczne obejmują niepełne dane i niewystarczającą próbę. Ich progi są zależne od celu biznesowego.

W MVP upoważnienie operatora zapisuje osobne interaktywne polecenie z podglądem planu. W trybie bez interakcji wymagany jest istniejący rekord upoważnienia. W lokalnym środowisku agent z pełnym dostępem do sekretów i plików może obejść taki mechanizm; mocniejsza kontrola wymaga oddzielnego procesu wykonawczego z poświadczeniami zapisu.
