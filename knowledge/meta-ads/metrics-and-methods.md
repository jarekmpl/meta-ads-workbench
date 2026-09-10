# Metryki i metody analizy

Wersja 0.1, 2026-09-09. Poniżej znajdują się autorskie definicje robocze i metody do recenzji. Przykłady liczbowe są **syntetyczne**, niezwiązane z kontami klientów. Nie stanowią benchmarków branżowych ani gotowych progów decyzyjnych.

## Umowa dotycząca metryki

Przed użyciem nowego wskaźnika zapisujemy: nazwę, licznik, mianownik, źródło, jednostkę, poziom obiektu, okno/czas atrybucji, datę/kohortę, regułę agregacji i sposób obsługi braków. Zmiana definicji wymaga wersji. Nie mieszamy kliknięć wszystkich, kliknięć linku, kliknięć wychodzących, odsłon strony docelowej i sesji.

| Metryka | Robocza definicja | Warunek i pułapka |
| --- | --- | --- |
| CPM | wydatki / wyświetlenia × 1000 | Ta sama waluta i zakres |
| CTR linku | kliknięcia linku / wyświetlenia × 100% | Nie zastępuj CTR wszystkich kliknięć |
| CPC linku | wydatki / kliknięcia linku | Nie oznacza kosztu wizyty ani klienta |
| CPL | przypisany koszt reklam / zdefiniowane leady | Jedna definicja zdarzenia; nie suma aliasów |
| CPQL | przypisany koszt reklam / unikalne leady kwalifikowane | CRM, definicja kwalifikacji i dojrzała kohorta |
| Koszt sprzedaży z leadów | przypisany koszt reklam / zdefiniowane sprzedaże z kohorty | Ten sam zakres pozyskania i czas na domknięcie |
| CPA zakupu | wydatki / zakupy według ustalonej definicji | Zamówienie nie zawsze jest opłaconą sprzedażą |
| ROAS Meta | wartość zakupów przypisana przez Meta / wydatki | Zapisz definicję wartości, walutę i atrybucję |
| Średnia wartość zakupu | wartość zakupów / liczba tych samych zakupów | Ten sam zbiór zdarzeń; nie łącz przychodu CRM z innym mianownikiem |
| Koszt nowego klienta z reklamy | przypisany koszt reklam / nowi klienci według sklepu/CRM | Nie nazywaj pełnym CAC, jeśli nie uwzględnia innych kosztów pozyskania |
| Kwalifikacja | kwalifikowane leady / unikalne leady danej kohorty | Ta sama definicja i moment oceny |
| Domknięcie sprzedaży | sprzedaże / leady kwalifikowane danej kohorty | Nie dziel sprzedaży ze starych leadów przez nowe leady miesiąca |
| Przejście na stronę | LPV / właściwe kliknięcia prowadzące na stronę | Diagnostyczny iloraz zdarzeń; nie zawsze odsetek unikalnych osób |
| Konwersja sesji | sesje z wynikiem / uprawnione sesje | Wspólny system pomiaru; nie mieszaj sesji GA z wszystkimi konwersjami Meta |
| Częstotliwość | wyświetlenia / zasięg | Zasięg dla całego zakresu; nie suma dziennych zasięgów |
| Tempo realizacji budżetu | wydatki do dnia / uzgodniony plan do dnia | Plan może być nieliniowy |

Przy mianowniku zero wskaźnik jest niedostępny z powodem `zero_denominator`. Brak pomiaru daje `unavailable`. Te sytuacje nie są zerowym kosztem lub zerowym ROAS. Wskaźniki agregujemy z sum liczników i mianowników; nie liczymy zwykłej średniej CPA/CTR kampanii. Reach i wskaźniki oparte na unikalnych osobach wymagają odrębnego raportu dla odpowiedniego zakresu.

## Dobór porównań

- **Zmiana w czasie:** równe, dojrzałe okresy i podobny układ dni tygodnia; oznacz promocje, sezonowość i zmiany konfiguracji.
- **Odchylenie od celu:** cel uzgodniony dla konkretnego produktu/rynku/wyniku. Benchmark z innego konta jest kontekstem, nie obowiązującą normą.
- **Porównanie obiektów:** wspólny wynik, okno pomiaru i ograniczenia biznesowe. Oddziel koszt od skali i jakości.
- **Kohorty:** grupuj według daty pozyskania, a sprzedaż oceniaj po porównywalnym czasie. Przy istotnych różnicach terminów nie udawaj dojrzałych wyników.
- **Eksperyment:** zaplanowany kontrast i metoda przypisania grup. Wybór najlepszego obiektu po fakcie pozostaje rankingiem obserwacyjnym.

„Ostatnie 7 dni względem poprzednich 7” i „ostatnie 28 względem poprzednich 28” to użyteczne propozycje okien, a nie wymóg Mety. Właściwy wybór zależy od cyklu konwersji, sezonowości i pytania. Dla konta bez historii opisujemy ograniczenie zamiast tworzyć pozorny benchmark.

## Rozkład kosztu wyniku

Niech `S` oznacza wydatki, `I` wyświetlenia, `C` kliknięcia linku, `O` uzgodnione wyniki. Dla dodatnich mianowników:

```text
CPM = 1000 × S / I
CTR_fraction = C / I
Q = O / C
koszt wyniku = S / O = CPM / (1000 × CTR_fraction × Q)
```

To tożsamość arytmetyczna dla wspólnych zakresów. `Q` jest jedynie ilorazem wyników i kliknięć. Jeżeli `O` obejmuje także konwersje po wyświetleniu, wiele zdarzeń na osobę lub inne ścieżki, `Q` nie jest prawdopodobieństwem konwersji klikającego. Nie wolno wtedy opisywać równania jako ścisłego lejka osób. Do takiej interpretacji potrzebujemy spójnego pomiaru kliknięcia i jego dalszego wyniku.

Przykład: `S=1000`, `I=100000`, `C=1000`, `O=20`. CPM=10, CTR=1%, Q=2%, koszt wyniku=50. W kolejnym porównywalnym okresie CPM=15, a oba ilorazy pozostają takie same: koszt wyniku wynosi 75. Arytmetycznie zmianę wyjaśnia koszt wyświetleń. Nie dowodzi to wzrostu konkurencji — potrzebne są m.in. dane o miksie emisji, stawkach i zmianach kampanii.

Gdy wiele składowych się zmienia, można pokazać ich ilorazy między okresami. Nie sumujemy procentowych zmian jako wkładów w zmianę CPA. Przy zerach rezygnujemy z ilorazowego rozkładu i opisujemy wolumeny.

## Leady: tani kontakt a wartościowa szansa

Dwie przykładowe kampanie, ta sama waluta, spójne kohorty i definicja kwalifikacji:

| Kampania | Wydatki | Leady | Kwalifikowane | CPL | CPQL |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1000 | 100 | 10 | 10 | 100 |
| B | 1200 | 60 | 30 | 20 | 40 |

B ma dwukrotnie wyższy CPL, ale niższy CPQL i więcej kwalifikowanych kontaktów. To podstawa do dalszej oceny jakości, nie automatycznego przeniesienia całego budżetu: trzeba sprawdzić domknięcia, marżę, dojrzałość, obsługę i potencjał zwiększenia skali.

W kohorcie rozróżniamy: zgłoszenie → poprawny/unikalny lead → kwalifikacja → kontakt → spotkanie/oferta → sprzedaż. Specjalista może zmienić etapy dla branży. Definicję i opóźnienie każdego etapu zapisujemy. Wysoki udział braku kontaktu może wynikać zarówno z jakości danych, jak i z czasu reakcji zespołu; sama tabela nie rozstrzyga przyczyny.

## E-commerce: próg pokrycia kosztu reklamy

Niech `R` będzie uzgodnioną wartością sprzedaży, a `m` udziałem marży kontrybucyjnej **przed reklamą**, po tych kosztach zmiennych, które uzgodniliśmy uwzględniać. W uproszczonym modelu:

```text
wkład po reklamie = R × m − wydatki reklamowe
ROAS pokrywający koszt reklamy = 1 / m
```

Dla m=40% próg wynosi 2,5. To nie dowodzi pełnej rentowności firmy: model pomija nieuwzględnione koszty stałe i nie rozstrzyga przyrostowości sprzedaży. Jeśli marża ma inną bazę przychodu niż wartość w ROAS Meta, nie porównuj tych liczb bez uzgodnienia. Zwroty i podatki uwzględnij zgodnie z przyjętą definicją wartości; nie odejmuj ich drugi raz w marży.

Dla pozyskiwania nowych klientów odrębnie uzgadniamy koszt pierwszego zakupu, przewidywaną wartość w horyzoncie, koszt ponownego zakupu i czas zwrotu. LTV bez definicji horyzontu oraz walidacji kohort jest hipotezą.

## Analiza kreacji

Proponowana taksonomia materiałów: `concept_id`, produkt/oferta, potrzeba odbiorcy, główna obietnica, rodzaj dowodu, otwarcie, format, CTA, język, data publikacji i relacja do wcześniejszych wariantów. Przykładowe koncepcje: demonstracja zastosowania, odpowiedź na obiekcję, historia klienta, porównanie rozwiązań. To kategorie do ustalenia przez zespół, nie obowiązkowy zestaw reklam.

Metryki otwarcia i utrzymania uwagi są diagnostyczne. „Hook rate” lub „hold rate” bez ustalenia licznika/mianownika nie jest porównywalną metryką. Materiały o różnej długości, miejscu emisji i celu nie powinny być porównywane wyłącznie jednym wskaźnikiem obejrzenia. Nie przenosimy wyników zagregowanych kreacji automatycznych na konkretny komponent bez danych pozwalających go wyodrębnić.

Wynik kreatywny łączymy z wynikiem biznesowym i ekspozycją. Agent ma wskazać, czy problem dotyczy zainteresowania, obietnicy/oferty, doświadczenia po kliknięciu, jakości leadów czy też nie jest jeszcze rozstrzygalny.

## Plan oceny eksperymentu

Karta testu zawiera pytanie, hipotezę, warianty, metrykę główną, metryki ochronne, sposób tworzenia grup, uzasadnienie próby/horyzontu, budżet ryzyka i moment analizy. Uwzględnia sposób zakończenia przy braku danych oraz przy zdarzeniu wymagającym przerwania. Różnica procentowa jest efektem biznesowym, a nie samodzielnym dowodem statystycznym.

Nie wybieramy „zwycięzcy” tylko dlatego, że ma najwyższy punktowy ROAS po wielu porównaniach. Metody modelujące niepewność wymagają założeń dopasowanych do danych. Duża liczba kliknięć nie gwarantuje dostatecznej próby sprzedaży. Przy analizach obserwacyjnych nie używamy etykiety „dowiedziony efekt zmiany”.

## Wybór dalszego działania

Najpierw usuń niepewność, która zmienia decyzję: uzgodnij zdarzenie, sprawdź dojrzałość, pozyskaj brakującą konfigurację. Następnie wybierz najmniejszy sensowny test rozróżniający hipotezy. Nie produkuj długiej listy zmian jednocześnie, jeśli później nie będzie wiadomo, co pomogło.

Każda rekomendacja powinna odpowiadać: co wiemy, czego nie wiemy, co sprawdzimy, jaki jest koszt/ryzyko, kiedy ocenimy i co będzie wynikiem sukcesu lub porażki. Brak danych to konkretna pozycja do uzupełnienia, a nie pretekst do dowolnej porady.
