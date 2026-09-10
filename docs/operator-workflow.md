# Codzienna praca specjalisty i kontekst klientów

## Organizacja

Repozytorium GitHub zawiera narzędzie i wspólne metody pracy. Instalator tworzy osobną kopię roboczą dla każdego klienta, z własnym środowiskiem Python i bez połączenia z repozytorium Git. Przykład:

```text
MetaAds/
  installer/                  kod pobrany z GitHuba
  clients/
    klient-a/                 osobny projekt i rozmowy agenta
      workspace.json          stały kod i nazwa klienta
      context/                prywatny kontekst i jego indeks
      projects/               briefy, decyzje i testy poszczególnych działań
      config/local/           konfiguracja jednego konta Meta
      secrets/                lokalne poświadczenia
      data/                   baza tego klienta
      reports/                analizy i ich dowody
      output/                 dokumenty do przekazania
      skills/                 procedury tej wersji systemu
      knowledge/              wspólna wiedza tej wersji systemu
    klient-b/                 niezależna kopia
```

Obecna wersja obsługuje jedno konto Meta na przestrzeń. Jeśli klient ma kilka kont, utwórz oddzielne przestrzenie o kodach np. `klient-a-pl` i `klient-a-de`. Kontekst wspólny importuj jawnie do każdej z nich. Raportów, tokenów ani baz nie łącz. Wspólny profil klienta z wieloma kontami i synchronizacja kontekstu są dalszym rozszerzeniem.

Python sprawdza klienta, zgodność skonfigurowanego konta, miejsce bazy i ścieżki plików obsługiwanych przez CLI. Blokuje wyjście poza katalog, obcą konfigurację, część obejść przez dowiązania oraz użycie demo w przestrzeni klienta. Nie jest to izolacja systemu operacyjnego: agent z dostępem do całego komputera może użyć innych narzędzi. Ogranicz uprawnienia agenta do projektu. Jeśli potrzebna jest ścisła izolacja, uruchamiaj klientów na osobnych kontach systemowych lub w odrębnych środowiskach z osobnymi poświadczeniami.

Nie dodawaj katalogu `clients/` jako jednego projektu agenta. Nie zapisuj ustaleń klienta w globalnych instrukcjach ani pamięci wspólnej narzędzia. Osobna rozmowa sama w sobie nie zastępuje osobnego katalogu.

## Kontekst bez zamkniętej listy kategorii

Materiały mogą obejmować strategię, cele, sezonowość, notatki, ton komunikacji, brandbook, kalendarz promocji, ograniczenia oferty, badania odbiorców lub dowolny inny temat. Pole `type` przyjmuje własną nazwę. Jedyny wymagany materiał wejściowy to plik i jego tytuł; resztę można uzupełniać w miarę pracy.

Indeks `context/index.json` przechowuje klienta oraz ID, tytuł, typ, projekt, tagi, status, datę dodania, opcjonalne daty dokumentu i ważności, poprzednią wersję, ścieżkę oraz SHA-256 materiału. Od wersji 0.5 Python odczytuje PDF, DOCX, TXT i Markdown, wyszukuje fragmenty oraz porównuje notatki. Reguły w `context/rules.json` zachowują wykorzystane cytaty i historię decyzji. [Proces kontekstu](client-context.md) opisuje komendy, konflikty i podstawę rekomendacji. OCR nie jest częścią obecnej wersji.

Statusy:

- `draft` oznacza materiał przyjęty do odczytu, którego ustalenia nie są jeszcze potwierdzoną zasadą działania.
- `confirmed` oznacza ustalenia potwierdzone przez operatora dla opisanego zakresu.
- `superseded` zachowuje wcześniejszą wersję, która przestała obowiązywać.

Agent może korzystać z roboczego materiału jako tła z odpowiednim oznaczeniem. Nie przedstawia go jako decyzji klienta. Potwierdzenie kontekstu nie oznacza zgody na jakiekolwiek zmiany w Meta.

Przykład importu dla agenta:

```bash
python3 workbench.py context add --file context/inbox/spotkanie.md --title "Ustalenia przed promocją" --type meeting --document-date 2026-09-08 --project jesien --tag oferta --valid-until 2026-11-30
python3 workbench.py context list
python3 workbench.py context status --id ID_Z_IMPORTU --status confirmed --reason "Operator potwierdził zakres ustaleń w rozmowie"
```

Nie wpisuj dosłownie `ID_Z_IMPORTU`: użyj identyfikatora zwróconego przez import. Agent może wykonać te kroki na prośbę „dodaj do kontekstu”. Jeżeli operator od razu potwierdza przekazane ustalenia, nie trzeba pytać ponownie o tę samą decyzję.

Plik zewnętrzny można importować przez jawną ścieżkę `--file`; jest to celowy wyjątek od ograniczenia odczytu do katalogu klienta. Import kopiuje materiał, nie zmienia źródła. Operator wskazuje, że należy on do tego klienta. Rejestr nie potrafi sam rozpoznać właściciela dokumentu.

Nową wersję importujemy jako nowy materiał z opcjonalnym `--version-of ID_POPRZEDNIEJ_WERSJI`. Nie nadpisujemy poprzedniej. Zmiana oryginału w `context/materials/` powoduje błąd kontroli integralności i blokuje potwierdzenie. Agent oznacza poprzednią wersję jako zastąpioną dopiero po ustaleniu, co nowy materiał zastępuje. Data ważności jest sygnałem do sprawdzenia, nie poleceniem automatycznego kasowania.

## Początek dnia lub nowej rozmowy

1. Otwórz projekt właściwego klienta. Agent odczytuje `workspace.json`, `capabilities` i indeks kontekstu.
2. Podaj zadanie, np. „Sprawdź wyniki z ostatnich siedmiu pełnych dni i zaproponuj trzy najważniejsze działania”.
3. Agent dobiera aktualne materiały dotyczące zadania. Nie wczytuje wszystkich dokumentów ani innych klientów. Przy zadaniu dla konkretnego projektu uwzględnia zarówno jego ustalenia, jak i obowiązujące zasady marki.
4. Jeśli nowe ustalenie koliduje ze starszym, agent opisuje konkretną różnicę i pyta o rozstrzygnięcie. Najnowsza data pliku nie daje automatycznie pierwszeństwa.

Wskazana w rozmowie decyzja ma pierwszeństwo w bieżącym zadaniu w granicach uprawnień. Agent zapisuje zmianę kontekstu, jeśli ma obowiązywać dalej. Dokumenty klienta nie mogą uchylać zakazu kasowania ani wymagania akceptacji zmian.

## Analiza i decyzje

Każda analiza otrzymuje osobny katalog `reports/RRRR-MM-DD-temat/`. Dla HTML w tym katalogu znajdują się tylko `raport.html` i `materialy/`. Dane, obliczenia, źródła dowodów, wykorzystane ID kontekstu i jego wersje, notatkę analityczną oraz kontrolę języka zapisujemy w `materialy/`. Gotowy PDF trafia do `output/`. W rozmowie operator dostaje konkretne rekomendacje, a istotny brak danych jest opisany razem z następnym krokiem.

Dla dłuższego projektu używaj `projects/KOD/`: brief, lista decyzji, plan testów i stan następnych działań. Szablony w `templates/client-context/` są opcjonalne. Nie trzeba zakładać każdego pliku przed pierwszą analizą.

Na końcu pracy agent zapisuje krótkie przekazanie w projekcie: co sprawdzono, co ustalono, co czeka na odpowiedź i jaki jest następny krok. Taki zapis pozwala kontynuować w innym narzędziu LLM. Nie przenoś całej rozmowy z danymi do projektu innego klienta.

## Przegląd tygodniowy

Specjalista sprawdza wyniki, otwarte rekomendacje, rezultaty zakończonych testów i zbliżające się zmiany oferty. Agent wskazuje wygasające lub sprzeczne materiały. Do wspólnego kompendium mogą trafiać wyłącznie świadomie opracowane, pozbawione danych klienta zasady po recenzji. Import kontekstu nie dopisuje niczego do `knowledge/`.

## Kopie zapasowe, zespół i aktualizacje

Kopię katalogu klienta przechowuj w zatwierdzonym firmowym miejscu z dostępem tylko dla właściwych osób. Poświadczenia obsługuj zgodnie z firmowym sposobem przechowywania sekretów; plik `600` nie jest zaszyfrowanym sejfem. Nie dodawaj przestrzeni klientów do repozytorium narzędzia. Ich `.gitignore` domyślnie pomija wszystko.

Nie udostępniaj jednocześnie aktywnej bazy SQLite przez dysk synchronizowany między operatorami. Wyznacz właściciela danej sesji pracy; przekazuj zamknięte kopie i zatwierdzone dokumenty. Rejestr kontekstu blokuje równoległy lokalny zapis, ale nie jest systemem współpracy wielu komputerów.

Aktualizacja kodu jest oddzielnym działaniem. Przed nią zatrzymaj pracę i zadbaj o kopię klienta. Od wersji 0.6 używaj update.py według [instrukcji aktualizacji](updating.md). Skrypt chroni pliki użytkownika i wykrywa lokalne poprawki w plikach narzędzia. Starszą instalację rozpoznaje przez oryginalną paczkę bazową. Nie używamy `git pull`, nadpisywania całego katalogu ani `--resume` jako aktualizacji kodu.

## Cele i historia decyzji od wersji 0.3

[Proces celów i rekomendacji](goals-and-recommendations.md) opisuje trwałe definicje wyników, przypisania kampanii, terminy oraz ocenę testów. Przed kolejną analizą agent odczytuje te ustalenia przez skill meta-ads-decisions. Raporty Meta dołączają obliczenia i historię z chwili tworzenia; eksport PDF uwzględnia oba elementy. Rejestr pozostaje w przestrzeni klienta i wymaga kopii razem z danymi.

## Kreator kampanii 0.4

[Instrukcja kreatora](campaign-wizard.md) opisuje przygotowanie nowej kampanii w rozmowie, zapis stanu i kontrolowane tworzenie nowych obiektów PAUSED. Skorzystaj ze skilla meta-ads-campaign-wizard. Zgody, briefy i dziennik w data/campaign-wizard.sqlite3 należą do danych klienta i powinny być objęte kopią zapasową. Pierwsza instalacja zachowuje tryb read_only.

## Dokumenty i ustalenia od wersji 0.5

Do pytań o komunikację, porównań spotkań i doboru podstaw rekomendacji używaj skilla meta-ads-context. Po imporcie notatki agent odczytuje treść, zestawia ją z dotychczasowymi zasadami i proponuje konkretne aktualizacje. Zatwierdzone ustalenia można dołączyć do rekomendacji przez `context basis`. Kopią zapasową obejmuj cały `context/`, także oryginały materiałów i rejestr reguł.

## Własne metody specjalisty

Przed analizą agent odczytuje aktywne wytyczne z [profilu specjalisty](specialist-guidance.md). Profil może być wspólny dla kilku klientów, ale zawiera wyłącznie ogólne metody. Ograniczenia marki, cele i materiały konkretnego klienta pozostają w jego kontekście. Aktualizacje narzędzia nie zmieniają żadnej z tych dwóch warstw.
