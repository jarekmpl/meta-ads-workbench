# Dokumenty i ustalenia klienta

Od wersji 0.5 agent może odczytywać tekst PDF, treść i tabele DOCX oraz pliki TXT i Markdown zapisane w UTF-8. Wyszukuje fragmenty lokalnie, porównuje notatki i zapisuje uzasadnione ustalenia. Cały proces działa w katalogu jednego klienta. Nie wymaga zewnętrznej bazy wektorowej ani dodatkowego modelu. Agent rozmowny, z którego korzystasz, interpretuje odnalezioną treść zgodnie z uprawnieniami swojego środowiska.

Operator może powiedzieć:

> Dodaj ten brandbook i notatkę ze spotkania do kontekstu promocji jesiennej.

> Które zasady komunikacji obowiązują w tej promocji we wrześniu?

> Co zmieniliśmy na ostatnim spotkaniu i co z tego wynika dla reklam?

Agent stosuje [meta-ads-context](../skills/meta-ads-context/SKILL.md). Poniższe komendy służą agentowi; operator nie musi ręcznie przygotowywać JSON.

## Import i odczyt

```bash
python3 workbench.py context add --file context/inbox/spotkanie.docx --title "Spotkanie o promocji jesiennej" --type meeting --project jesien --document-date 2026-09-08 --valid-from 2026-09-01 --valid-until 2026-09-30
python3 workbench.py context read --id ID_MATERIALU --output output/odczyt.json
python3 workbench.py context search --query "komunikacja" --project jesien --as-of 2026-09-10
```

Wstaw ID zwrócone przez import. `read` zwraca tekst i odwołania do fragmentów: klienta, ID materiału, SHA-256 oryginału, ID fragmentu, tytuł, lokalizację oraz cytat. Lokalizacja wskazuje stronę PDF, akapit lub wiersz tabeli DOCX albo linię tekstu. Białe znaki w cytatach są ujednolicone. Dłuższe fragmenty mają części do 2400 znaków.

`search` wyszukuje słowa bez rozróżniania wielkości liter i polskich znaków, a trafienia szereguje według pokrycia zapytania. Nie wykonuje pełnego wyszukiwania semantycznego. Agent dobiera krótkie zapytania i odmiany słów. Wynik zawiera `coverage` z błędami odczytu i ostrzeżeniami. Dokumenty są odczytywane ponownie z oryginałów; nie ma nieaktualnego indeksu tekstu ani usługi działającej w tle. Przy dużym zbiorze materiałów odczyt może potrwać dłużej.

Podanie projektu obejmuje jego materiały i kontekst ogólny. Bez projektu dostajesz tylko kontekst ogólny. Domyślnie wyszukiwanie pomija zastąpione materiały oraz te poza podaną datą ważności. `--history` dołącza te materiały, zachowując ich oznaczenia. Propozycje pozostają widoczne z `material_status: draft`.

Dane wejściowe mają limit 50 MB, tekst po odczycie 2 mln znaków, PDF 1000 stron, XML treści Worda i strumień strony PDF po 10 MB. Odczyt DOCX obejmuje główną treść i tabele; pomija nagłówki, stopki, komentarze i załączniki. Nie otwiera odnośników ani nie uruchamia makr. Śledzone zmiany wymagają importu uzgodnionej wersji przed potwierdzeniem reguł. Pliki DOC i skany bez warstwy tekstowej wymagają wcześniejszej konwersji lub OCR. Puste strony są oznaczane, a nie traktowane jako dowód braku ustaleń. Złożone tabele PDF mogą wymagać obejrzenia strony.

## Ustalenia, które można zastosować

Materiał jest dokumentem; reguła jest konkretnym ustaleniem odczytanym z tego dokumentu. Jeden brandbook może uzasadniać wiele reguł. Kontrakt opisuje `schemas/context_rule.schema.json`. Przykład struktury:

```json
{
  "schema_version": "1.0",
  "kind": "context_rule",
  "client_id": "klient-a",
  "rule_id": "jesien-zwracanie-sie-1",
  "key": "communication.address",
  "value": "W promocji jesiennej zwracamy się do odbiorcy na Ty.",
  "project": "jesien",
  "valid_from": "2026-09-01",
  "valid_until": "2026-09-30",
  "sources": ["TU_AGENT_WSTAWIA_OBIEKT_ODWOLANIA_Z_ODCZYTU"]
}
```

To ilustracja, nie gotowy plik wejściowy: element `sources` trzeba zastąpić rzeczywistym obiektem z `chunks` lub `hits[].reference`. Gotowy przykład ze sztucznymi materiałami i prawidłowymi odwołaniami tworzy test `tests/test_context.py`. Samego SHA ani cytatu nie wolno wymyślać.

```bash
python3 workbench.py context rule-add --file output/ustalenie.json
python3 workbench.py context status --id ID_MATERIALU --status confirmed --reason "Operator potwierdził ustalenia z notatki"
python3 workbench.py context rule-status --id jesien-zwracanie-sie-1 --status confirmed --expected-revision 1 --actor "Operator" --reason "Potwierdzenie treści, zakresu i dat w rozmowie"
python3 workbench.py context rules --project jesien --as-of 2026-09-10
```

Import i `rule-add` tworzą propozycje. Potwierdzenie zapisuje rzeczywistą decyzję operatora; treść dokumentu ani sam agent nie są autorem tej zgody. Reguły są niezmienne: poprawka wymaga nowego ID. Zmiany statusu zachowują autora, powód, datę i numer rewizji w `context/rules.json`. Pole `revision` dotyczy stanu reguły, a SHA-256 określa wersję dokumentu.

Termin stosowania reguły jest częścią wspólną jej dat i dat wszystkich materiałów, na których się opiera. Brak dat oznacza brak ograniczenia, nie pozwolenie na ich wymyślenie. `as-of` filtruje daty ważności, ale korzysta z **bieżących statusów rejestru**. Nie rekonstruuje automatycznie wiedzy zespołu z przeszłości; do tego służy zapisana podstawa wcześniejszej rekomendacji.

## Sprzeczności

Różne wartości tego samego `key` w tym samym projekcie i dniu trafiają do `conflicts`; dotyczy to także reguły ogólnej i reguły promocji. Obie przestają być dostępne jako podstawa nowej rekomendacji. Różnica względem propozycji pojawia się w `potential_conflicts`; propozycja nie unieważnia zatwierdzonej reguły. Silnik sygnalizuje różnicę wartości. Agent sprawdza, czy jest to rzeczywista sprzeczność, inne sformułowanie tej samej zasady czy wyjątek.

Klucze nie są zamkniętym słownikiem. Agent uzgadnia nazewnictwo z istniejącym rejestrem i wykrywa również sprzeczności między różnie nazwanymi zagadnieniami. Nie ma tu automatycznego rozumienia wszystkich sprzeczności w dowolnym tekście. Cytat przechodzi kontrolę zgodności z plikiem, a trafność interpretacji pozostaje zadaniem agenta i operatora.

Przy decyzji o zastąpieniu reguły:

```bash
python3 workbench.py context rule-status --id STARE_ID --status retired --expected-revision 2 --actor "Operator" --reason "Uzgodniony rabat 20% zastępuje wcześniejsze 10% w tej promocji"
```

Nie ma automatycznego pierwszeństwa nowszej daty ani projektu nad marką. Wyjątek czasowy trzeba zapisać jako uzgodnione, nienakładające się zakresy. Nie wycofuj całej strategii, gdy zmienia się tylko rabat jednej promocji. Pozostałe reguły starego dokumentu mogą nadal obowiązywać.

## Zmiany między spotkaniami

```bash
python3 workbench.py context meetings --project jesien --output output/zmiany-spotkan.json
python3 workbench.py context compare --before STARSZE_ID --after NOWSZE_ID
```

`meetings` wybiera dwa ostatnie materiały typu `meeting` według `document_date`, w dokładnie tym samym projekcie. Brak dat lub remis wymaga wskazania dwóch ID. `compare` pokazuje dodane, usunięte i zmienione fragmenty wraz z odwołaniami. Agent opisuje znaczenie zmian i oddziela ustaloną decyzję od propozycji. Pominięcie tematu w nowej notatce samo w sobie nie uchyla wcześniejszego ustalenia. Komendy porównania nie zmieniają reguł ani statusu materiałów.

## Podstawa rekomendacji

```bash
python3 workbench.py context basis --project jesien --as-of 2026-09-10 --rule jesien-zwracanie-sie-1 --used-for "Dobór formy zwracania się do odbiorcy w testowanym tekście" --output output/podstawa-rekomendacji.json
```

Wynik wstawiamy do pola `context_basis` rekomendacji. Zawiera wykorzystane ID i pełne definicje reguł, datę i projekt zastosowania, fragmenty dokumentów, ich hashe oraz opis wykorzystania. `recommendations add` ponownie sprawdza zgodność klienta i projektu celu, integralność dokumentów, statusy, daty i konflikty. Zapis podstawy jest chroniony tą samą lokalną blokadą co zmiany kontekstu.

Wcześniejsze rekomendacje zachowują swoją podstawę nawet po wycofaniu reguły. Powtórzenie zapisu tej samej rekomendacji zwraca dawny wpis. Nowa rekomendacja podlega aktualnej kontroli. Pole jest opcjonalne dla zgodności ze starszymi danymi oraz propozycji wynikających wyłącznie z wyników kampanii. Agent ma obowiązek je dodać, gdy korzysta z ustaleń klienta; nie wolno usuwać go w celu obejścia błędu walidacji.

Odwołania pozostają w historii rekomendacji i notatkach analitycznych. Treść raportu nadal skupia się na działaniach i ich uzasadnieniu. Rejestr kontekstu nie jest zgodą na zmianę w Meta i nie znosi zakazu kasowania.
