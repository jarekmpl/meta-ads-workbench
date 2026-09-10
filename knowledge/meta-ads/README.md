# Kompendium analizy Meta Ads

Wersja **0.3**, 2026-09-10. Autor pierwszej redakcji: agent projektu. Status: **robocze wytyczne analityczne, przed recenzją specjalistów Meta Ads**. Cel: powtarzalne, uzasadnione analizy oraz uczenie się na wynikach kampanii.

Kompendium opisuje, jak dochodzić do wniosków. Silnik Python pobiera i oblicza dane; agent dobiera reguły, interpretuje wyniki i przedstawia rekomendacje. Sama obecność reguły w pliku nie oznacza, że silnik już pobiera wymagane dane albo automatycznie ją wykonuje. Wersja 0.3 służy do analiz i planowania testów; nie upoważnia do zmian reklam.

Sposób przedstawiania wyników określa [standard rekomendacji](../../docs/analysis-standard.md): konkretne zmiany i testy na początku, dane jako uzasadnienie. Reguły, ich wersje i warunki zastosowania zapisuj w wewnętrznym śladzie analizy, bez przytaczania ich w raporcie. Jest to standard pracy ustalony przez użytkownika, odrębny od roboczych wytycznych dziedzinowych.

## Co warto analizować

| Obszar | Pytanie biznesowe | Metody i wynik analizy | Reguły |
| --- | --- | --- | --- |
| Jakość danych | Czy temu raportowi można zaufać? | Kompletność, definicje zdarzeń, atrybucja, opóźnienia, deduplikacja | DQ-01–04 |
| Wynik biznesowy | Czy pozyskujemy wartościowych klientów? | Koszt kwalifikowanego leada, kohorty sprzedaży, marża, nowi/powracający klienci | LD-01, EC-01 |
| Struktura i cel | Czy system optymalizuje właściwy wynik i ma warunki do uczenia? | Cel → zdarzenie → KPI, fragmentacja, historia zmian | ST-01–03 |
| Emisja i budżet | Co ogranicza wynik i gdzie powstaje zmiana kosztu? | Brak emisji, CPM/CTR/wynik po kliknięciu, realizacja planu wydatków | PE-01–03 |
| Kreacje i oferta | Które pomysły przyciągają właściwych odbiorców? | Różnorodność koncepcji, zgodność reklamy z ofertą, trendy zużycia | CR-01–02 |
| Odbiorcy i umiejscowienia | Czy ograniczenia pomagają osiągać cel? | Segmenty, zmiana udziałów w emisji, kontrolowane testy automatyzacji | AU-01, PE-04 |
| Eksperymenty | Czy zmiana rzeczywiście pomogła? | Testy A/B, grupy kontrolne, rozróżnienie atrybucji i przyrostu | EX-01–02 |
| Planowanie i skalowanie | Co uruchomić lub zmienić jako następne? | Kontrola briefu, zdolność obsługi, budżet ryzyka, plan oceny | PL-01, OP-01 |

Meta wskazuje pięć kierunków w Performance 5: uproszczenie konta, automatyzację, różnicowanie kreacji, jakość danych i weryfikację wyników. Traktujemy je jako punkt wyjścia. Konkretne testy diagnostyczne i wyjątki w tym kompendium są naszą propozycją metod pracy, a nie cytatem ani kompletną listą wymagań Mety. [Źródło M01](sources.md#m01).

## Dokumenty i kolejność czytania

- [Zasady analizy](analysis-rules.md): 20 kart reguł z danymi wejściowymi, sygnałem, działaniem i ograniczeniami.
- [Praktyczne zasady optymalizacji](optimization-practice.md): 12 kart OPT-01–12 dotyczących celu, kreacji, tekstów, CTA, umiejscowień, odbiorców, remarketingu, formularzy, testów i skalowania.
- [Metryki i metody](metrics-and-methods.md): definicje, porównania, diagnostyka zmian i przykłady.
- [Źródła](sources.md): dokładne materiały, co potwierdzają, data sprawdzenia oraz braki w weryfikacji.
- [Wkład specjalistów](specialist-contribution.md): szablon reguły, rejestrowanie dowodów, parametrów i wyjątków.
- [Scenariusze kontrolne](review-cases.md): przykłady do oceny, czy agent stosuje zasady poprawnie.
- [Przegląd E01: automatyzacja](contributions/E01-automation-review.md): przyjęte kierunki, rozstrzygnięte konflikty i zakres zastosowania.
- [Historia zmian](CHANGELOG.md): wersje kompendium i uzasadnienia zmian.

Przy rekomendacjach dotyczących optymalizacji przeczytaj także karty OPT odpowiadające zadaniu: OPT-01 dla celu i zdarzenia, OPT-02–05 dla kreacji i tekstów, OPT-06–08 dla dystrybucji i odbiorców, OPT-09 dla formularzy, OPT-10–12 dla testów, diagnozy i skalowania. Karty OPT doprecyzowują dotychczasowe reguły; nie zastępują kontroli danych.

Przed audytem przeczytaj ten indeks. Z kart wybierz te, które odpowiadają pytaniu i dostępnym danym; nie wczytuj wszystkich materiałów źródłowych do każdej analizy. Do diagnozy zmiany kosztu potrzebne będą np. DQ-01–03 i PE-02, a do oceny jakości leadów także LD-01.

## Kolejność rozumowania

1. **Cel i zakres.** Ustal klienta, konto, rynek, okres, produkt/ofertę, wynik biznesowy i ograniczenia. Brak celu nie blokuje raportu opisowego, ale ogranicza ocenę skuteczności.
2. **Wiarygodność.** Sprawdź źródło, kompletność, definicje konwersji, walutę, strefę, atrybucję i dojrzałość danych. Zaznacz konkretnie, które oceny blokuje brak danych.
3. **Wynik.** Pokaż wolumen i koszt wyniku oraz porównywalny punkt odniesienia. Sam procent zmiany bez licznika i mianownika jest niewystarczający.
4. **Diagnoza.** Przejdź od konta do kampanii, zestawu i reklamy tylko tam, gdzie są dane. Rozdziel obserwację, możliwe wyjaśnienia i dowody potrzebne do ich rozróżnienia.
5. **Decyzja.** Zaproponuj zbieranie danych, sprawdzenie konfiguracji, test, plan zmiany albo pozostawienie ustawień. Nie wymuszaj interwencji.
6. **Ocena skutku.** Określ wynik, horyzont, limit ryzyka i warunek przerwania testu. Zapamiętaj później, czy hipoteza się potwierdziła, zamiast dopisywać sukces na podstawie samego wykonania zmiany.

## Jak agent stosuje reguły

Wspólne oznaczenia podstawy: **META** — wąskie twierdzenie potwierdzone źródłem Mxx; **METODA** — nasza zasada analityczna, definicja lub tożsamość arytmetyczna; **HIPOTEZA** — związek do sprawdzenia; **EKSPERT** — opinia specjalisty z nazwiskiem/autorem, datą i zakresem. **PUBLICYSTYKA** — zewnętrzny materiał doradczy E01, inspiracja do oceny i testów, bez statusu dokumentacji Mety lub recenzji naszego eksperta. Reguły mogą łączyć podstawy; źródło platformy nie potwierdza automatycznie całej naszej procedury.

Spośród 20 kart bazowych PE-03/04, ST-01, CR-01, AU-01 i EX-01 mają wersję 0.2, pozostałe 0.1. Dodatkowe karty OPT-01–12 mają wersję 0.3. Wszystkie zachowują `status: guidance`, `expert_review: pending`. Można ich używać jako wskazówek z zachowaniem warunków. Nie zawierają zatwierdzonych parametrów automatycznego wyłączania lub skalowania. Hipotez nie przedstawiaj jako potwierdzonych przyczyn.

Dla każdej zastosowanej karty wybierz wynik:

| Wynik reguły | Znaczenie |
| --- | --- |
| `observation` | Opis poparty liczbami lub odczytaną konfiguracją |
| `hypothesis` | Możliwe wyjaśnienie, wymagające sprawdzenia |
| `test_candidate` | Test z celem i warunkami oceny |
| `insufficient_data` | Brakuje konkretnych danych do tej oceny |
| `not_applicable` | Reguła nie pasuje do celu, formatu lub sytuacji |
| `no_action` | Dane nie uzasadniają zmiany teraz |

Ślad analizy powinien wskazywać: `knowledge_version`, `rule_id`, `rule_version`, `source_refs`, konto/obiekt, okres, `snapshot_id`, obserwację, wymagane/brakujące dane, zastosowane parametry z ich pochodzeniem, wynik reguły i rekomendację. Zapisuj go w osobnej notatce analitycznej obok raportu; nie dopisuj ręcznie pól do oryginalnego JSON silnika. Silnik nie ma jeszcze automatycznego rejestru wykonania tych reguł. Dla kart OPT pomijaj `source_refs` dotyczące treści wytycznych zgodnie z zasadami tego modułu; nadal zapisuj dowody z danych kampanii i warunki zastosowania.

Pewność opisuj jako pewność **obserwacji** i osobno pewność **wyjaśnienia**. Poprawnie policzony wzrost CPA nie oznacza wysokiej pewności, że przyczyną jest kreacja. Nie twórz procentowego „confidence” bez modelu statystycznego.

Priorytet wynika z możliwego wpływu biznesowego, wiarygodności dowodów i pilności. Potwierdzony problem danych blokujący ocenę ma pierwszeństwo przed kosmetyką kreacji. Nie podawaj przewidywanego oszczędzonego budżetu lub przyrostu sprzedaży bez jawnego modelu i założeń.

## Co działa w naszym systemie teraz

| Poziom dostępności | Zakres |
| --- | --- |
| Dostępne dane Meta | Kampanie i ich statusy/cel Meta; dzienne wydatki, wyświetlenia, kliknięcia linku; osobne typy zdarzeń; specyfikacja i kontrola sum snapshotu |
| Możliwe obecnie | Kontrola zakresu, raport emisji, identyfikacja braku wydatków, część porównań kosztu ruchu po obliczeniu ich w Pythonie |
| Działa po jawnym przypisaniu | Koszt wyniku i ROAS, dokładny klucz zdarzenia, porównania okresów Meta, ocena progów i historia testów; [proces](../../docs/goals-and-recommendations.md) |
| Wymaga dalszego wdrożenia | Ocena dojrzałości konwersji, eksperymenty A/B i harmonogram cyklicznych ocen |
| Wymaga dodatkowych odczytów | Zestawy, reklamy, kreacje, ustawienia odbiorców/umiejscowień, budżety, uczenie, historia zmian, reach/frequency za cały okres, diagnostyka pomiaru |
| Wymaga danych biznesowych lub eksperymentu | Kwalifikacja i sprzedaż CRM, marża/zwroty, nowi klienci, zdolność obsługi, przyrost wyniku wywołany reklamą |

Opis metody nie oznacza gotowej komendy. `capabilities` i rzeczywisty `coverage` raportu mają pierwszeństwo przy ocenie dostępności. Nie zastępuj brakujących danych Meta danymi demo.

## Co chcemy ustalić ze specjalistami najpierw

1. Jak definiujemy lead, lead kwalifikowany, sprzedaż i wartość zakupu w poszczególnych typach biznesu?
2. Jaki horyzont i wolumen uzasadniają decyzję, biorąc pod uwagę opóźnienie sprzedaży i ryzyko klienta?
3. Kiedy łączymy lub rozdzielamy strukturę, a kiedy zachowujemy wyjątek biznesowy?
4. Jak opisujemy koncepcje kreacji i rozpoznajemy zużycie na podstawie kilku sygnałów?
5. Jak projektujemy testy i skalowanie, aby później ocenić wynik?

Zaczynamy od LD-01, EC-01 i CR-01/02: definicje wyniku i praktyka kreatywna nadadzą pozostałym analizom właściwy kontekst. Nie potrzebujemy od razu zbioru setek porad.
