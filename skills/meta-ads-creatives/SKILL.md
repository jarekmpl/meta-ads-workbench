---
name: meta-ads-creatives
description: Analizuj treść i wyniki istniejących reklam Meta, przygotuj karty kreacji i hipotezy testów. Używaj do przeglądu grafik, karuzel, filmów oraz różnorodności i możliwego zużycia kreacji. Nie tworzy ani nie publikuje reklam.
---

# Analiza kreacji Meta

Pracuj z katalogu projektu. Polecenie użytkownika obejmuje potrzebne odczyty i lokalny raport. Nie wysyłaj materiałów do dodatkowego dostawcy AI bez uzgodnienia. Agent z obsługą obrazu ogląda lokalne materiały; agent tekstowy oznacza ocenę obrazu jako niedostępną. Żadna komenda Python nie zastępuje oglądania reklamy.

## Pobranie i dobór

Odczytaj [AGENTS.md](../../AGENTS.md), `meta-ads capabilities` oraz CR-01/02, DQ-01/02/03, PE-02/04, ST-01 i EX-01 w [kompendium](../../knowledge/meta-ads/analysis-rules.md). Ustal cel biznesowy, konto i okres. Domyślnie 30 pełnych dni do wczoraj w strefie konta, porównanie z poprzednim równym okresem. Nie stosuj progu jednego klienta do innych klientów lub celów.

```bash
.venv/bin/meta-ads creatives collect --client CLIENT --account ACCOUNT --last-days 30 --sample-size 20 --directory reports/RUN
.venv/bin/meta-ads creatives media --client CLIENT --account ACCOUNT --directory reports/RUN
```

`collect` zapisuje wyniki wszystkich reklam z okresu, kontrolne sumy konta, 1-50 wybranych reklam wraz z ustawieniami, wyniki dzienne wybranej próby, podział umiejscowień i statystyki wideo. To oddzielny zbiór dowodów, nie snapshot standardowego silnika. Dobór celowy obejmuje kampanie, wydatki i małą ekspozycję; nie jest reprezentatywnym badaniem ani eksperymentem. Wielkość próby służy organizacji przeglądu, nie potwierdza istotności wyniku. Sprawdź `errors`, rozbieżności sum i faktyczne pokrycie materiałów. Opcjonalny błąd nie jest zerowym wynikiem. Przy bardzo wielu kampaniach jawnie wskaż pominięte zakresy.

`media` odczytuje obrazy i dostępne filmy z CDN Mety oraz przygotowuje lokalne kadry przez ffmpeg. Połączenia i podpisane adresy pozostają w prywatnych danych; nie publikuj surowych odpowiedzi ani adresów CDN w raporcie. Powtórzenie `collect` w niedokończonym katalogu wznawia zgodne odczyty, a nie odświeża dane. Po ukończeniu użyj nowego katalogu dla nowego odczytu. Materiały otrzymują SHA-256; hash identyfikuje plik, nie koncepcję.

## Ocena materiału

1. Najpierw obejrzyj materiał i przeczytaj tekst; opisz treść bez uzasadniania jej późniejszym wynikiem. Użyj [karty i kryteriów](references/review-card.md). Nie twierdź, że ocena była zaślepiona, jeśli znałeś już wyniki.
2. Rozdziel reklamę (`ad_id`), obiekt kreacji (`creative_id`), poszczególne materiały i koncepcję. Przy karuzeli zachowaj kolejność kart; lista pobranych obrazów nie dowodzi kolejności emisji. Przy wariantach `asset_feed_spec` i automatycznych zmianach opisuj dostępne elementy, nie jeden rzekomo pewny wygląd każdej emisji. Nie rozdzielaj wyników reklamy na materiały bez danych wariantowych.
3. Każda obserwacja wskazuje fragment tekstu, plik/obszar grafiki albo timestamp filmu. Ocena czytelności w umiejscowieniu wymaga podglądu tego umiejscowienia. Sam plik 1:1 nie dowodzi ucięcia w Reels. Nie odczytuj drobnego tekstu z niewyraźnej miniatury jako pewnego cytatu.
4. Film oceniaj na podstawie pełnego materiału, obrazu i dźwięku. Kadry pozwalają opisać widoczne sceny i napisy, ale nie wystarczają do oceny montażu, tempa i narracji. Bez dźwięku lub transkrypcji oznacz brak; nie wymyślaj wypowiedzi. Bez odczytu strony/formularza nie potwierdzaj zgodności reklamy z ofertą.
5. Zapisz ocenę treści przed interpretacją wyników. Nie nadawaj pozornej obiektywności przez jeden wynik 0-100. Oddziel jakość wykonania, wynik i siłę dowodów. Zachowaj oryginalną polszczyznę cytowanych reklam; miodkuj dotyczy naszego komentarza.

## Wyniki i rekomendacje

Stosuj [standard rekomendacji](../../docs/analysis-standard.md). Wyprowadź z przeglądu konkretne poprawki i briefy nowych wariantów: co zmienić w obrazie lub tekście, na jakiej podstawie i jak ocenić efekt. Raport zaczynaj od priorytetów. Galeria i metryki uzasadniają te propozycje. Brak zakupów w danych nie blokuje opracowania pomysłów na podstawie obejrzanych materiałów; wskaż wymagany pomiar przy planie testu. Wytyczne i alternatywne wyjaśnienia zachowaj w notatce, a w raporcie uwzględnij te różnice interpretacji, które zmieniają zalecane działanie.

Licz Pythonem. Porównuj zgodne zdarzenia, okna atrybucji, cele, oferty, okresy i możliwie podobne warunki. Nie sumuj aliasów konwersji ani zasięgów dziennych. `null` jawnego okna działania oznacza brak raportowanej wartości, nie potwierdzone zero. Bieżące ustawienia nie dowodzą historycznej wersji reklamy.

Niskie wydatki nie dowodzą słabości; wysoki CTR nie dowodzi jakości leadów. Spadek CTR lub wzrost częstotliwości sam nie dowodzi zużycia. Statystyki wideo porównuj z uwzględnieniem długości i definicji pól. Ranking obserwacyjny nie jest testem A/B; kilka reklam w zestawie nie gwarantuje losowego podziału ekspozycji. Wspólny materiał na dwóch `ad_id` nadal może mieć różne teksty, odbiorców i warunki.

Dla rekomendacji zapisz obserwację, hipotezę, alternatywne wyjaśnienia, proponowany wariant, główną metrykę, warunki porównania i brakujące dane. Progi próby, budżetu lub przerwania testu pochodzą z ustaleń ekonomicznych i projektu eksperymentu, nie z uniwersalnej liczby dni. Brak danych może prowadzić do propozycji pomiaru lub braku zmiany.

## Wynik pracy

Przygotuj raport z galerią, kartami materiałów, wynikami, ograniczeniami, pokryciem próby i briefami testów. Zachowaj źródłowe JSON oraz osobny plik ocen agenta i wersję kompendium. Przykłady klienta przechowuj w `reports/`, nie we wspólnej wiedzy. Poprawki specjalisty zapisuj osobno z autorem i datą; dopiero po recenzji proponuj zmianę zasad.

`creatives report --client CLIENT --account ACCOUNT --directory reports/RUN --assessment reports/RUN/materialy/content-assessment.json --notes reports/RUN/materialy/interpretation.json` tworzy HTML i Markdown po zapisaniu oceny. Format plików i ograniczenia renderera opisuje [dokumentacja procesu](../../docs/creative-analysis.md). Sprawdź wygenerowane liczby, linki do materiałów i wygląd galerii.

Zastosuj [miodkuj](../miodkuj/SKILL.md) i zapisz kontrolę językową zgodnie z AGENTS.md. Lokalny HTML z galerią jest artefaktem raportowym, nie opublikowaną stroną. PDF wykonuj na żądanie według [meta-ads-pdf](../meta-ads-pdf/SKILL.md); obecny standardowy generator PDF nie obsługuje galerii. Nie deklaruj gotowego PDF bez jego wykonania i kontroli stron.

Przy raporcie HTML stosuj układ z AGENTS.md: w katalogu raportu tylko `raport.html` i `materialy/`. Wszystkie pliki pomocnicze, w tym JSON, grafiki, notatki i kontrola językowa, trafiają do `materialy/`. Jeśli PDF towarzyszy temu HTML, także zapisz go w `materialy/` i podaj bezpośredni link do PDF. Sprawdź względne odnośniki po wygenerowaniu.
