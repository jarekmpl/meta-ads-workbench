# Projekt procesu przygotowania kampanii

Wersja propozycji: **1.0, 2026-09-10**. To specyfikacja do wdrożenia. Rozmowa z zapisem stanu, automatyczne badanie witryny i generator planów nie są jeszcze funkcjami silnika. Obecny model `CampaignBrief` stanowi punkt wyjścia; zapis do Meta pozostaje niedostępny.

## Wynik procesu

Operator opisuje zamiar własnymi słowami. System zbiera potrzebne dane, proponuje sposób prowadzenia kampanii i przygotowuje kompletny pakiet do oceny: brief, strukturę, nazwy, budżety, harmonogram, treści, materiały, pomiar oraz pierwszy test. Każdy brak ma wskazaną osobę lub metodę jego uzupełnienia.

Planowanie nie wymaga zgody na zapis na koncie. Gotowy plan zmian wymaga osobnej, wyraźnej akceptacji użytkownika zgodnie z [polityką zmian](account-change-policy.md). Nie kasujemy żadnych obiektów. Domyślnie tworzymy obiekty wstrzymane; aktywację obejmuje odrębny plan.

## 1. Rozpoznanie zadania

System ustala klienta, konto, ofertę i oczekiwany wynik. Wykorzystuje wcześniejsze ustalenia i profil klienta. Gdy konto jest jednoznaczne, nie pyta ponownie o jego wybór. Przy kilku dopasowaniach pokazuje nazwy i identyfikatory do rozstrzygnięcia.

Pierwsza runda obejmuje najwyżej trzy potrzebne pytania, np.:

- „Co promujemy i jaki wynik chcesz uzyskać: zapytania, zakupy czy zapisy?”
- „Podaj stronę oferty, jeśli nie ma jej jeszcze w profilu klienta.”
- „Jaki budżet mamy do dyspozycji i kiedy kampania ma działać?”

System pyta tylko o informacje, których nie ma. Operator może odpowiedzieć „nie wiem”. Wtedy system przedstawia warianty wraz z uzasadnieniem, a nierozstrzygniętą decyzję zachowuje w briefie. Budżetu i terminu uruchomienia nie ustala za operatora.

## 2. Samodzielne pozyskanie informacji

| Miejsce | Co system odczytuje | Co robi z wynikiem |
| --- | --- | --- |
| Profil klienta | Uzgodnione cele, rynki, języki, ograniczenia marki, zasoby i wcześniejsze ustalenia | Wypełnia znane pola; sprawdza aktualność zmiennych warunków |
| Witryna | Oferta, ceny, warunki promocji, warianty produktu, argumenty, FAQ, sposób kontaktu lub zakupu | Przygotowuje opis oferty i kandydatów do komunikacji; wskazuje niezgodności |
| Konto Meta, w dostępnym zakresie odczytu | Waluta, strefa, strony i tożsamości, formularze, katalogi, źródła zdarzeń, konfiguracja i wyniki podobnych kampanii | Weryfikuje zasoby i proponuje ich wykorzystanie; brak dostępu zapisuje jako brak |
| Materiały klienta | Księga marki, zdjęcia, filmy, oferta, zaakceptowane komunikaty | Ocenia przydatność do planowanych reklam i wskazuje brakujące warianty |

System otwiera istotne podstrony oferty, formularza, koszyka lub rejestracji w zakresie dostępnego odczytu. Nie wysyła formularzy, nie dokonuje zakupów ani nie zmienia witryny. Tekst strony i plików traktuje jako dane, a nie instrukcje. Nie wyprowadza ze strony założeń o budżecie, marży, prawach do materiałów ani zdolności obsługi klientów. Nie kopiuje automatycznie informacji między klientami.

Dla znalezionego faktu zapisuje adres lub referencję zasobu, datę odczytu i krótki dowód. Publiczna cena jest informacją znalezioną; warunki konkretnej kampanii potwierdza operator. Techniczny odczyt identyfikatora zasobu nie wymaga osobnego pytania, ale wybór tego zasobu musi być widoczny w planie.

## 3. Pytania zależne od celu

Typ wybieramy dla projektu lub kampanii. Jeden klient może równocześnie sprzedawać produkty, pozyskiwać leady i organizować wydarzenia.

| Ścieżka | Pytania, które trzeba rozstrzygnąć |
| --- | --- |
| Leady | Co oznacza dobry lead? Formularz Meta czy strona? Jakie dane i pytania kwalifikujące są potrzebne? Kto i jak szybko obsłuży zgłoszenia? Jaki jest docelowy CPL lub koszt kwalifikowanego leada? Czy można pobrać późniejszy wynik z CRM? |
| E-commerce | Jakie produkty i rynki promujemy? Czy oferta, ceny i dostępność są aktualne? Czy mamy katalog? Czy zakup, wartość i waluta są poprawnie mierzone? Jaki CPA lub ROAS przyjmujemy i czy uwzględnia on marżę oraz zwroty? Czy celem są nowi klienci, wszystkie zamówienia czy konkretny asortyment? |
| Bezpłatne rejestracje | Co jest wynikiem: wysłanie formularza czy potwierdzony zapis? Ile miejsc jest dostępnych? Kiedy kończą się zapisy? Jaki koszt zapisu akceptujemy? Czy będziemy mierzyć późniejszy udział? |
| Sprzedaż biletów | Gdzie odbywa się zakup? Jakie są ceny, pula miejsc i terminy? Czy możemy mierzyć zakup? Jeśli nie, jakie wcześniejsze działanie możemy mierzyć i zaakceptować jako cel pomocniczy? |

Wspólne ustalenia obejmują także rynek, język, odbiorców, wykluczenia, budżet i jego rodzaj, daty ze strefą czasową, ograniczenia oferty, kategorie szczególne, materiały i osobę akceptującą. System pyta o kategorie lub ograniczenia tylko z odpowiednim kontekstem; nie uznaje braku informacji za potwierdzenie, że nie występują.

Brak ustalonego CPA nie musi blokować testu. Operator może zaakceptować plan poznawczy z budżetem, sposobem oceny i warunkiem zatrzymania. System nie wymyśla uniwersalnego kosztu wyniku.

Pytania techniczne poprzedza kontrola dostępnych zasobów. Zamiast prosić o numer formularza, system pokazuje pasujące formularze do wyboru. Zamiast pytać ogólnie o piksel, opisuje, jakie zdarzenie znalazł i czego jeszcze potrzebuje do planowanej konfiguracji.

## 4. Pamięć rozmowy

Każde pole briefu ma wartość, stan, pochodzenie, datę oraz powiązanie z decyzjami. Proponowane stany to: `missing`, `discovered`, `confirmed`, `conflict`, `unavailable`, `not_applicable`. Pole może być potwierdzone przez operatora lub odczyt techniczny; te rodzaje potwierdzenia zapisujemy osobno.

Rozmowa jest zapisywana po każdej odpowiedzi i może być wznowiona. System nie powtarza rozstrzygniętych pytań. Najpierw pyta o decyzje wpływające na resztę planu, następnie o zasoby, a na końcu o szczegóły wykonania. W jednej rundzie zadaje do trzech powiązanych pytań i krótko wyjaśnia ich znaczenie, jeśli nie jest oczywiste.

Zmiana celu, oferty, rynku lub strony uruchamia ponowną ocenę zależnych pól. Przykładowo zmiana formularza Meta na stronę unieważnia wybór formularza i wymaga sprawdzenia zdarzenia w witrynie. Poprzednie wersje pozostają w historii. Dane trwałe trafiają do profilu klienta, a budżet, daty i wariant oferty pozostają w briefie kampanii. Ustalenie dotyczące jednego projektu nie staje się automatycznie zasadą całego konta.

## 5. Projekt struktury i pomiaru

System najpierw zapisuje ciąg: **wynik biznesowy → dostępny pomiar → zdarzenie optymalizacji → KPI oceny**. Cel biznesowy, cel Meta i zdarzenie są osobnymi polami. Dostępność kombinacji ustawień musi być sprawdzona dla danego konta i wersji API przed wygenerowaniem planu wykonania.

Jeśli zakup jest poza dostępnym pomiarem, system proponuje najbliższy użyteczny sygnał. Dla sprzedaży biletów może to być kliknięcie prowadzące ze strony oferty do operatora biletowego. Plan określa przycisk lub link, warunek wywołania zdarzenia i sposób sprawdzenia, czy zdarzenie liczy się poprawnie. Dostępność tego zdarzenia do optymalizacji wymaga osobnej weryfikacji; samo dodanie go do raportu nie potwierdza takiej możliwości. Wdrożenie pomiaru jest osobnym zadaniem, a koszt takiego kliknięcia pozostaje oddzielony od kosztu sprzedaży.

Struktura ma odpowiadać decyzjom, które będziemy podejmować:

- Osobną kampanię proponujemy, gdy potrzebny jest inny cel Meta, niezależny budżet lub harmonogram, odrębny projekt albo inne istotne ograniczenie. Każdy podział otrzymuje uzasadnienie.
- Osobny zestaw proponujemy dla różnic wymagających osobnych ustawień emisji, zdarzenia, rynku, grupy odbiorców lub warunków testu. Nie rozbijamy automatycznie każdego zainteresowania na osobny zestaw.
- Reklamy rozróżniamy według koncepcji, argumentu, formatu i wersji treści. Zmiana rozmiaru tej samej grafiki jest wariantem wykonania, nie nową koncepcją.

| Wariant | Punkt wyjścia do propozycji | Powód ewentualnego podziału |
| --- | --- | --- |
| Leady | Wspólna oferta i definicja leada; dobrana lokalizacja konwersji | Inny proces obsługi, region z własnym budżetem, inna oferta lub test lokalizacji konwersji |
| E-commerce | Spójny rynek, ekonomika oferty i pomiar zakupu | Osobny budżet kategorii, istotnie inna marża/oferta, inny rynek lub uzasadniony test |
| Rejestracje i bilety | Jedno wydarzenie, termin oraz uzgodniony wynik | Inny wydarzeniowy budżet, rynek, pomiar lub etap oferty wymagający odrębnych ustawień |

Remarketing i pozyskiwanie nowych odbiorców nie są obowiązkowo osobnymi kampaniami. Wydzielamy je, gdy uzasadniają to cel, dostępna grupa, komunikat i kontrola budżetu. Rozróżniamy faktyczne ograniczenia odbiorców od sugestii dla automatyzacji. System ocenia, czy budżet i oczekiwana liczba wyników wystarczą do proponowanego podziału; nie stosuje stałej liczby kampanii, zestawów ani reklam dla każdego klienta.

Nazwy nadaje według [proponowanego standardu](campaign-naming-standard.md). Reguły planowania dobiera z kompendium: PL-01, ST-01–03, EX-01, OP-01 oraz odpowiednich OPT. Powiązania zapisuje wewnętrznie; operator otrzymuje uzasadnienie w zwykłym języku.

## 6. Pakiet do oceny

Operator otrzymuje:

1. Krótki opis tego, co promujemy, komu i jaki wynik chcemy uzyskać.
2. Drzewo kampanii, zestawów i reklam z nazwami oraz uzasadnieniem podziału.
3. Dokładne budżety, walutę, poziom ich ustawienia, harmonogram i status początkowy. Budżetu kampanii nie sumujemy ponownie przy każdym zestawie. Oddzielamy plan wydatków od limitów rzeczywiście egzekwowanych przez platformę.
4. Dla każdej reklamy: tożsamość, tekst, nagłówek, CTA, materiał lub brief materiału, format, adres docelowy i plan oznaczeń analitycznych. Brief grafiki nie zastępuje gotowego pliku. Podgląd lokalny nie zastępuje późniejszej kontroli reklamy w Mecie.
5. Plan pomiaru: definicję wyniku, źródło zdarzeń, mapowanie KPI, wymagane prace i kontrolę poprawności. Oznaczenia URL nie zawierają danych osobowych; zastosowane makra wymagają weryfikacji obsługi.
6. Pierwszy test: hipotezę, warianty, metodę porównania, główną metrykę, budżet, termin oceny i warunek przerwania. Zwykłego porównania reklam nie nazywamy eksperymentem losowym.
7. Listę braków oddzielającą kwestie blokujące przygotowanie planu od prac możliwych do wykonania później.

System proponuje konkretny wariant, a alternatywy pokazuje wtedy, gdy operator musi rozstrzygnąć istotny wybór. Nie obiecuje przewidywanych wyników bez modelu i jawnych założeń.

## 7. Walidacja i zgoda na zapis

Rozróżniamy stan rozmowy od gotowości do wykonania. Można mieć kompletny brief i jednocześnie czekać na materiały. Można mieć poprawny lokalny plan i nie mieć zgody na jego wysłanie.

Przyszły walidator sprawdza zgodność klienta i konta, kompletność parametrów, walutę i budżety, terminy, zasoby, zdarzenie, ograniczenia kategorii, unikalność kluczy, nazwy i zależności nowych obiektów. Weryfikuje też, czy wybrany wariant jest obsługiwany przez wykonawcę. Brakujący identyfikator lub tekst zastępczy blokuje zależną operację. Nie zastępuje go przykładem demo.

Po walidacji powstaje wersjonowany plan z dokładnymi operacjami i hashem. Operator widzi konto, wszystkie obiekty, treści, zasoby, kwoty i statusy. Akceptacja briefu ani odpowiedzi na pytania nie oznaczają akceptacji zapisu. Zgoda dotyczy konkretnego planu; zmiana planu lub istotnej konfiguracji konta wymaga nowej zgody.

Wykonawca, gdy zostanie wdrożony, przed zapisem ponownie sprawdza zgodę i stan konta. Po utworzeniu obiektów wstrzymanych odczytuje je i porównuje z planem. Wynik częściowy zachowuje wraz z ID; nie kasuje obiektów po błędzie. Przy nieznanym wyniku uzgadnia stan przed ponowieniem operacji. Aktywacja jest osobnym, zatwierdzonym planem.

## Kolejność wdrożenia

1. **Rozmowa i lokalny brief.** Dodać wersjonowany zapis stanu oraz katalog pytań z warunkami, zależnościami i rozróżnieniem danych znalezionych oraz potwierdzonych. Nowy kontrakt powinien objąć rejestracje i cele pomocnicze; obecny model 1.0 wymaga jawnej migracji.
2. **Odczyt oferty i zasobów.** Dodać zbieranie faktów z witryny oraz inwentaryzację potrzebnych zasobów w dostępnym zakresie API. Nie oznaczać funkcji jako dostępnej przed jej wdrożeniem.
3. **Generator propozycji.** Dodać szablony zależne od celu, generator nazw i walidację. LLM prowadzi rozmowę i uzasadnia decyzje; Python zapisuje stan, generuje nazwy, liczy budżety i sprawdza kontrakty. Przenośny skill opisuje wspólny proces i korzysta z tych samych funkcji CLI.
4. **Pilot lokalny.** Sprawdzić brief leadowy, sklep, rejestrację i sprzedaż biletów z pomiarem pomocniczym. Następnie przeprowadzić rozmowę dla wskazanego klienta i przygotować lokalny pakiet bez zapisu na koncie.
5. **Kontrolowane tworzenie.** Wdrożyć wykonawcę według polityki zmian. Pierwszy zakres zapisu pozostaje zgodny z etapem 3 planu wdrożenia: leady i sprzedaż w witrynie z istniejącymi zasobami. Szerszy zakres planowania nie oznacza obsługi wszystkich wariantów zapisu.

Odbiór pierwszego etapu powinien sprawdzić, czy system wznawia rozmowę, nie powtarza odpowiedzi, wykrywa konflikt informacji, zmienia pytania po zmianie celu i nie uznaje briefu za zgodę. Kolejne scenariusze obejmują nieodczytywalną stronę, brak zasobów, błędne konto, brak pomiaru sprzedaży, zmieniony budżet oraz duplikaty nazw. Są to kryteria przyszłych testów, nie wyniki wykonanych testów.
