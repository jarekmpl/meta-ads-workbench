# Cele kampanii i historia decyzji

Od wersji 0.3 system zapisuje definicje wyników, cele kosztowe, przypisania kampanii i historię rekomendacji w `data/decisions.sqlite3`. Rejestr należy do przestrzeni klienta, tak jak dane z Meta. Nie trafia do repozytorium instalatora.

Operator rozmawia z agentem. Agent odczytuje kontekst, przygotowuje pliki i wykonuje komendy. Poniższa składnia służy utrzymaniu narzędzia; operator nie musi jej znać.

## Ustalenie celu

Możesz powiedzieć:

> W tym projekcie zależy nam na leadach z formularza Meta. Docelowy koszt leada to 50 zł. Zapisz ten cel dla wskazanych kampanii od początku września.

Agent najpierw odczytuje istniejące cele, kontekst oraz dostępne zdarzenia ze snapshotu. Ustala, co dokładnie jest wynikiem, gdzie powstaje i do których kampanii należy. Pyta o brakujące decyzje, korzystając z wcześniejszych odpowiedzi. Nie wyciąga definicji leada z samej nazwy kampanii ani jej celu reklamowego.

Cel zawiera projekt, oczekiwany wynik biznesowy, nazwę mierzonego zdarzenia, jego rolę, walutę i ewentualny docelowy koszt lub ROAS. W tej wersji jeden cel wskazuje dokładnie jeden `action_type` z dziennych danych Meta. Nie sumujemy aliasów tego samego zdarzenia.

Rola pomiaru określa sposób prezentacji:

- `primary` oznacza wynik główny, np. wysłanie formularza lub zakup.
- `proxy` oznacza sygnał pośredni, np. kliknięcie przycisku prowadzącego do sprzedawcy biletów.
- `diagnostic` oznacza wskaźnik pomocniczy.

Kliknięcie do serwisu biletowego może mieć własny koszt wyniku. System nie nazwie go zakupem i nie policzy dla niego ROAS. Samo zapisanie celu nie wdraża zdarzenia na stronie. Konkretny klucz kliknięcia musi być dostępny w danych; ogólny `link_click` nie identyfikuje automatycznie przejścia do danego sprzedawcy.

### Brak zdarzenia w danym dniu

Domyślne `missing_action_policy: unknown` pozostawia pełną liczbę wyników i koszt jako brak danych, jeżeli choć jednego dnia brakuje wybranego klucza. Dostępna suma pozostaje w `reported_results`. `zero_when_omitted` można zapisać, kiedy operator potwierdził, że pominięcie tego klucza oznacza zero dla przyjętego sposobu pobierania i pomiaru. Dotyczy to także dni uzupełnionych zerami emisji. Nie wybieraj tej reguły tylko po to, żeby uzyskać liczbę w raporcie.

### Wersje i daty

Definicja celu ma kolejne wersje. Każde przypisanie kampanii wskazuje konkretną wersję i datę początku obowiązywania. Nowa wersja celu nie przełącza kampanii samodzielnie; potrzebne jest nowe przypisanie. Dzięki temu zmiana docelowego CPL nie przelicza wcześniejszego okresu według nowego progu.

Przypisanie z tą samą datą może skorygować wcześniejszy wpis, zachowując go w historii. Nie można dopisać przypisania z datą wcześniejszą niż ostatnie zapisane. `goal_id: null` wraz z `goal_revision: null` kończy lokalne przypisanie od wskazanej daty. Kampania nadal istnieje na koncie.

Nowy raport używa aktualnego rejestru i przypisań obowiązujących w analizowanych dniach. Odtworzenie przez `report show` zwraca zapisany raport wraz z jego ówczesnymi definicjami i historią, bez ponownego przeliczania. Dwie wersje celu pozostają osobnymi grupami, nawet gdy mają tę samą nazwę.

## Rekomendacje, decyzje i testy

Po analizie agent sprawdza historię, a następnie zapisuje konkretne propozycje. Wpis zawiera działanie, uzasadnienie, kampanie, priorytet i odwołania do dowodów. Plan oceny określa hipotezę, okres bazowy, długość obserwacji, wskaźnik, kryterium sukcesu oraz warunek przerwania. Agent może zaproponować te parametry; nie przedstawia ich jako zaakceptowanych ustaleń operatora.

Przykładowa rozmowa:

> Zapisz ten test komunikatu. Za sukces przyjmijmy koszt leada do 40 zł po siedmiu pełnych dniach i co najmniej 10 leadach w każdym z porównywanych okresów.

> Akceptuję pomysł, ale wdrożenie zrobimy osobno.

> Zmianę wdrożyłem wczoraj. Zapisz tę datę i wróćmy do wyników po siedmiu dniach.

Rejestr obsługuje propozycję, akceptację pomysłu, odrzucenie, odłożenie z terminem, rozpoczęcie obserwacji, zakończenie bez oceny i ocenę wyniku. Każda decyzja ma autora, uzasadnienie i odwołanie do rzeczywistego ustalenia. `start` zapisuje potwierdzoną datę wykonanego wdrożenia; nie może wskazywać przyszłości ani nachodzić na okres bazowy. `note` dopisuje ustalenie bez zmiany statusu.

Akceptacja pomysłu w tym rejestrze nie daje uprawnień do zapisu w Meta. Sam rejestr nie zmienia konta. Osobny kreator 0.4 wymaga akceptacji własnego, dokładnego planu tworzenia. Również warunek przerwania jest instrukcją dla operatora; system sam nie wstrzymuje kampanii.

Odrzucony pomysł pozostaje w historii. Powtórzenie tego samego działania, celu w tej samej wersji i zestawu kampanii zwraca istniejący wpis. Ta kontrola porównuje znormalizowany tekst działania, nie jego znaczenie; agent dodatkowo sprawdza podobne pomysły. Świadomy powrót do tematu wymaga nowego ID, `followup_of` oraz `followup_reason`. Wcześniejsza decyzja pozostaje bez zmian.

## Ocena wyniku

Na początku kolejnej pracy agent odczytuje listę terminów. `--due` wskazuje odłożone lub trwające sprawy, których termin już nadszedł. Jest to sprawdzenie wykonywane na żądanie. Sam rejestr nie uruchamia agenta w tle i nie wysyła powiadomień.

Do oceny trzeba pobrać jeden snapshot obejmujący pełne oba okresy. Python porównuje te same kampanie i tę samą wersję celu. Przy zmianie przypisania lub brakującym zakresie blokuje ocenę. Nie usuwa przez to testu z historii.

Okresy mają równą długość od 1 do 90 dni. Początek obserwacji wynika z potwierdzonej daty wdrożenia. Termin oceny przypada po ostatnim pełnym dniu obserwacji. Porównanie domyślne `analyze` obejmuje ostatnie 7 pełnych dni oraz poprzednie 7 w strefie konta; można podać inny okres. Termin listy spraw jest liczony według lokalnej daty komputera; `--as-of` pozwala ją wskazać jawnie.

Wynik testu to spełnienie kryterium, niespełnienie lub brak rozstrzygnięcia. Próg liczbowy oznacza wartość bezwzględną, np. koszt do 40 zł; bez progu wymagana jest poprawa względem okresu bazowego. Opcjonalna minimalna liczba wyników dotyczy obu okresów. Brak pełnej metryki w którymkolwiek okresie oznacza brak rozstrzygnięcia. Zmiana procentowa od zera pozostaje nieobliczona.

Metody `before_after` i `observation` korzystają z takiego samego porównania opisowego. Nie jest to silnik eksperymentów A/B. Agent uwzględnia pozostałe zmiany, budżet i sezonowość przed przypisaniem poprawy konkretnemu działaniu. Zapisanej oceny nie nadpisujemy; kolejną próbę opisuje nowy wpis powiązany przez `followup_of`.

## Komendy i pliki

Przykładowe pliki w `examples/` zawierają wyłącznie dane syntetyczne. Przed użyciem agent zastępuje identyfikatory, daty i odwołania rzeczywistymi ustaleniami w przestrzeni klienta. Liczby dziesiętne w JSON zapisujemy jako tekst. `expected_revision: 0` tworzy cel lub pierwsze przypisanie. Przy aktualizacji podaj wersję z ostatniego odczytu; konflikt wymaga ponownego odczytu, a nie wymuszenia zapisu.

W zainstalowanej przestrzeni zastąp `meta-ads` przez `python3 workbench.py meta`. Parametry globalne, np. `--output`, muszą poprzedzać nazwę polecenia.

```bash
meta-ads goals list --client CLIENT --account ACCOUNT
meta-ads goals set --client CLIENT --account ACCOUNT --file context/goal.json
meta-ads goals assign --client CLIENT --account ACCOUNT --file context/assignment.json
meta-ads goals show --client CLIENT --account ACCOUNT --id GOAL --revision 1
meta-ads recommendations add --client CLIENT --account ACCOUNT --file context/recommendation.json
meta-ads recommendations event --client CLIENT --account ACCOUNT --file context/decision.json
meta-ads recommendations list --client CLIENT --account ACCOUNT --due
meta-ads recommendations show --client CLIENT --account ACCOUNT --id REC
meta-ads recommendations evaluate --client CLIENT --account ACCOUNT --id REC --expected-revision 3 --snapshot SYNC_ID
meta-ads --output reports/goal-review.json analyze --client CLIENT --account ACCOUNT --goal GOAL --since YYYY-MM-DD --until YYYY-MM-DD --snapshot SYNC_ID
```

Przypisanie celu i dodanie rekomendacji wymagają wcześniejszego snapshotu, aby sprawdzić ID kampanii. Komendy rejestru nie pobierają danych z sieci. `report campaigns` i `audit` automatycznie dołączają `goal_measurements` oraz aktualną historię rekomendacji. W wynikach Meta to `business_goal_status` oraz `goal_measurements` określają przypisania i obliczenia; stare pola `measurement_status` i `goal_groups` pozostają dla zgodności z formatem demo i nie opisują nowego mapowania.

`analyze` dla Meta zwraca `goal_review`. Eksport PDF obsługuje ten format, cele w raportach konta i historię rekomendacji. Przy dużym opracowaniu agent przygotowuje dokument z wybranymi tabelami i komentarzem zgodnie ze skillem PDF. Historia w raporcie odzwierciedla moment jego utworzenia, nie stan z ostatniego dnia okresu wyników.

## Kopie i aktualizacja

Kopia przestrzeni klienta powinna obejmować `data/decisions.sqlite3` razem ze snapshotami, kontekstem i raportami. Wykonuj ją po zakończeniu zapisów. Baza jest lokalna; nie jest wspólną usługą do równoczesnej pracy wielu komputerów. Dwa procesy na jednym komputerze mają kontrolę wersji i transakcje, które zapobiegają nadpisaniu cudzej decyzji.

Nowy rejestr powstaje przy pierwszym użyciu i nie zmienia starych snapshotów. Instalator 0.3 nadal tworzy nowe przestrzenie. Aktualizację istniejącej przestrzeni wykonaj według procesu wydania, po kopii zapasowej.

## Ustalenia klienta wykorzystane w rekomendacji

Od wersji 0.5 rekomendacja może zawierać `context_basis`: reguły, cytaty, wersje dokumentów, projekt, datę zastosowania i opis wykorzystania. Agent przygotowuje je komendą `workbench.py context basis`, a zapis rekomendacji sprawdza ich aktualność. [Proces kontekstu](client-context.md) opisuje wymagania i rozstrzyganie konfliktów. Stare rekomendacje pozostają czytelne i zachowują swoją pierwotną podstawę.
