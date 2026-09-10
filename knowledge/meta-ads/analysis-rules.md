# Karty zasad analizy

Metryka początkowa wszystkich 20 kart: `version: 0.1`, `status: guidance`, `expert_review: pending`, `created_at: 2026-09-09`. Znaczenie podstaw i wyników opisuje [indeks](README.md). Skróty Mxx i E01 prowadzą do [rejestru źródeł](sources.md). W wydaniu 0.2 karty PE-03, PE-04, ST-01, CR-01, AU-01 i EX-01 otrzymują `version: 0.2`, `updated_at: 2026-09-10`; pozostałe zachowują wersję 0.1. Status wszystkich pozostaje `guidance`, `expert_review: pending`. Reguły operują warunkowo: brak wymaganych danych daje `insufficient_data`, a nie domyślnie złą ocenę.

`Teraz` opisuje dostępność danych w obecnym systemie. Żadna karta nie jest nowym automatycznym detektorem Python. Progi procentowe, liczby dni i minimalne próby muszą mieć uzasadnienie w kontekście klienta lub planie testu; brak progu nie blokuje opisu obserwacji.

Przy tworzeniu rekomendacji używaj również [12 praktycznych kart OPT](optimization-practice.md). Doprecyzowują wykonanie analizy i planu testu; wersje powyższych 20 kart nie zmieniają się w wydaniu 0.3.

## DQ-01 — Definicja wyniku przed oceną kosztu

- **Podstawa:** METODA. **Zakres:** wszystkie raporty i cele. **Teraz:** dostępna kontrola braku mapowania; mapowanie Meta do wdrożenia.
- **Dane:** konto, waluta, cel biznesowy, nazwa zdarzenia, źródło wyniku, zasady deduplikacji i wartość wyniku. Przy celu sprzedażowym rozróżnij zamówienie, opłaconą sprzedaż i nowego klienta.
- **Sygnał:** kolumna „wyniki” łączy różne zdarzenia; występują aliasy akcji; brakuje profilu celu lub pojawia się zmiana definicji w czasie.
- **Postępowanie:** pokaż emisję i osobne zdarzenia, lecz wstrzymaj ocenę CPL/CPA/ROAS zależną od nieustalonej definicji. Zachowaj jedną uzgodnioną definicję dla porównania.
- **Nie wnioskuj:** suma `lead` i innego agregatu leadów oznacza dwukrotnie więcej kontaktów; cel kampanii `OUTCOME_SALES` dowodzi pomiaru zakupu; brak lokalnego profilu oznacza wadliwe ustawienia w Meta.
- **Ocena i wyjątki:** specjalista zatwierdza przykład mapowania na danych. Cele ruchu, zasięgu i zaangażowania mogą być prawidłowe — oceń je według briefu, nie wymuszaj KPI sprzedażowego.

## DQ-02 — Porównywalność i kompletność

- **Podstawa:** METODA. **Zakres:** każde porównanie. **Teraz:** specyfikacja, daty i kontrola sum dostępne; zaawansowane porównania do wdrożenia.
- **Dane:** pełne strony, okres, strefa, waluta, poziom obiektu, definicja kliknięcia/konwersji, atrybucja, czas przypisywania działania i czas pobrania.
- **Sygnał:** różnica między API i panelem, niepełny dzień, zmiana okna atrybucji, brak strony, odmienny zakres statusów lub zmiana udziału kampanii w portfelu.
- **Postępowanie:** uzgodnij specyfikacje; rozróżnij rzeczywistą zmianę wyniku od zmiany sposobu raportowania. Pokaż, które porównania pozostają użyteczne, a których nie można wykonać.
- **Nie wnioskuj:** brak wiersza lub błąd API to zero; różnica Meta–CRM zawsze oznacza awarię; suma dziennych zasięgów daje zasięg miesiąca.
- **Ocena i wyjątki:** sumy emisji uzgodnione, obie próby mają zgodne definicje. Dane finansowe CRM i atrybucja reklamowa mogą celowo przedstawiać różne perspektywy — nie dopasowuj ich na siłę.

## DQ-03 — Dojrzałość wyników i wielkość próby

- **Podstawa:** METODA. **Zakres:** rankingi, trendy, decyzje o zmianie. **Teraz:** częściowo; brakuje profili opóźnienia konwersji.
- **Dane:** wolumen i wydatki, opóźnienie zdarzeń, historia dopisywania konwersji, data pozyskania leada, data oceny sprzedaży, kontekst promocji i dni tygodnia.
- **Sygnał:** silny procentowy ruch przy kilku zdarzeniach; wynik ostatnich dni jeszcze dojrzewa; okna mają inną strukturę dni; wniosek powstał po wielu porównaniach segmentów.
- **Postępowanie:** pokaż wielkości bezwzględne, dojrzały okres i niepewność. Dla CRM porównuj kohorty o podobnym czasie na konwersję. Przed testem uzgodnij minimalny wykrywalny efekt i metodę oceny próby.
- **Nie wnioskuj:** trzy dni zawsze wystarczą; dowolne 50 wyników oznacza istotność statystyczną; brak istotności dowodzi braku efektu. Nie stosuj testu dwumianowego do modelowanych lub ułamkowych konwersji bez uzasadnienia modelu.
- **Ocena i wyjątki:** termin ponownej oceny zależy od cyklu biznesu. Potwierdzone błędy dostępu czy błędny adres docelowy można diagnozować od razu; nie trzeba czekać na próbę konwersji.

## DQ-04 — Pomiar, deduplikacja i spójność zdarzeń

- **Podstawa:** META M06 — identyfikacja wspólnych zdarzeń; METODA — procedura kontroli. **Teraz:** brak diagnostyki Pixel/CAPI.
- **Dane:** źródła zdarzeń, kontrolowane zdarzenia testowe, identyfikatory/nazwy zdarzeń, czas, wartość i waluta, agregaty sklepu lub CRM, diagnostyka błędów.
- **Sygnał:** skok konwersji po dodaniu CAPI, zakup bez wartości, zmiana waluty lub duża zmiana relacji źródeł bez podobnej zmiany biznesu.
- **Postępowanie:** prześledź to samo zdarzenie przeglądarkowe i serwerowe. SDK opisuje użycie `event_id` z `event_name` do rozpoznawania identycznych zdarzeń. Sprawdź spójność wartości i uzgodnij zakres z systemem biznesowym.
- **Nie wnioskuj:** więcej zdarzeń oznacza więcej sprzedaży; wysoki wskaźnik dopasowania potwierdza brak duplikatów; sam niski wskaźnik uzasadnia podnoszenie budżetu lub dowolne poszerzanie zbieranych danych.
- **Ocena i wyjątki:** kontrolowane zdarzenie ma oczekiwany przebieg bez podwójnego policzenia. Raportowane wyniki nie muszą zrównać się z CRM z powodu różnych zasad atrybucji. Zasada nie obejmuje zbierania danych osobowych do kompendium.

## PE-01 — Brak emisji i ograniczona emisja

- **Podstawa:** METODA. **Teraz:** identyfikacja zera emisji; pełna diagnoza wymaga odczytów.
- **Dane:** wydatki/wyświetlenia, aktualne statusy kampanii, zestawów i reklam, harmonogram, budżet, limity, strategia stawek i komunikaty o dostarczaniu.
- **Sygnał:** brak lub spadek emisji w okresie, w którym kampania miała działać.
- **Postępowanie:** najpierw potwierdź poprawne pobranie danych i oczekiwaną emisję. Potem zbadaj statusy, terminy i komunikaty, a następnie ograniczenia budżetu, stawek i odbiorców. Kolejność jest procedurą diagnostyczną, nie twierdzeniem o przyczynie.
- **Nie wnioskuj:** `ACTIVE` kampanii oznacza działające reklamy; zero wydatków oznacza awarię; trzeba zwiększyć budżet, choć reklamy są odrzucone lub zestawy wstrzymane.
- **Ocena i wyjątki:** wskazany odczytany powód albo lista nierozstrzygniętych możliwości. Gdy wstrzymanie było planowane, wynikiem jest `no_action` lub wybór okresu z emisją.

## PE-02 — Rozłożenie zmiany CPA/CPL na składowe

- **Podstawa:** METODA. **Teraz:** CPM/CTR/CPC dostępne; dalszy lejek wymaga mapowania i danych.
- **Dane:** porównywalne okresy, wydatki, wyświetlenia, kliknięcia linku i spójnie zdefiniowane wyniki; opcjonalnie LPV, sesje i zdarzenia lejka.
- **Sygnał:** koszt wyniku rośnie lub spada.
- **Postępowanie:** sprawdź zmianę CPM, CTR linku i relacji wyników do ruchu. Rozdziel koszt dotarcia, reakcję na reklamę i etap po przejściu do oferty. Wzory i ograniczenia: [metody](metrics-and-methods.md). Gdy zmienia się kilka czynników, pokaż je łącznie bez przypisywania całej zmiany jednemu.
- **Nie wnioskuj:** wyższy CPM sam dowodzi konkurencji; spadek CTR sam dowodzi złej kreacji; iloraz konwersji uwzględniających wyświetlenia i kliknięć jest współczynnikiem konwersji osób klikających.
- **Ocena i wyjątki:** obserwację arytmetyczną zamień w listę testowalnych wyjaśnień. Najpierw sprawdź PE-04 — zmiana miksu emisji może zmienić średnią bez pogorszenia poszczególnych segmentów.

## PE-03 — Tempo wydatków względem planu

- **Podstawa:** METODA. **Teraz:** historia wydatków; brak planów i odczytu budżetów.
- **Dane:** uzgodniony limit okresu, harmonogram, wydatki, budżety kampanii/zestawów, waluta, daty promocji i ograniczenia obsługi.
- **Sygnał:** realizacja planu odbiega od zaplanowanego przebiegu.
- **Postępowanie:** porównaj wydatki z planem narastająco. Projekcję na koniec okresu oznacz jako scenariusz zakładający utrzymanie tempa, nie prognozę gwarantowaną. Sprawdź, czy budżet należy do kampanii, czy zestawu, aby nie policzyć go dwa razy.
- **Nie wnioskuj:** dzienny budżet jest zawsze sztywnym dziennym limitem pobrania; brak równego wydawania każdego dnia oznacza błąd; niewydany budżet należy wydać bez względu na koszt wyniku.
- **Ocena i wyjątki:** kontroluj faktyczny limit biznesowy; kampanie promocyjne mogą mieć celowo nierówny rozkład. Przygotowanie konkretnej zmiany wymaga aktualnych ustawień i osobnej procedury wykonania.

- **Uzupełnienie 0.2 — plan testu budżetu (METODA, inspiracja E01):** zestaw udział wydatków z uzgodnionym priorytetem produktu i warunkami eksperymentu. Jeżeli obecna alokacja uniemożliwia zaplanowane porównanie, przygotuj wariant budżetu na poziomie zestawów lub dostępnych limitów. Podaj kwoty wynikające z planu testu, koszt wyniku i kryterium zachowania skali; brakujące parametry pozostaw do ustalenia. Stabilnej kampanii spełniającej cel nie przebudowuj tylko z powodu nierównego podziału. Harmonogram testuj na podstawie wyników w czasie i dostępności oferty, z uwzględnieniem opóźnień konwersji.

## PE-04 — Segmenty i zmiana miksu emisji

- **Podstawa:** METODA. **Teraz:** tylko segmentacja po kampanii/celu Meta; inne podziały niedostępne.
- **Dane:** porównywalne segmenty kraju, urządzenia, umiejscowienia, produktu lub typu odbiorcy; wolumen i udział każdego segmentu.
- **Sygnał:** średnia konta pogarsza się, a wyniki podobnych obiektów są stabilne; mały segment wygląda wyjątkowo dobrze lub źle.
- **Postępowanie:** oddziel zmianę wewnątrz segmentów od zmiany ich udziałów. Szukaj segmentów diagnostycznie; decyzję potwierdź na kolejnych danych lub testem. Zgłoś niedostępne kombinacje podziałów.
- **Nie wnioskuj:** segment bez raportowanych wyników miał zero sprzedaży; wynik małej grupy jest stabilny; wykluczenie najsłabszego umiejscowienia zachowa dotychczasowy koszt pozostałych.
- **Ocena i wyjątki:** wynik pokaż z udziałem w wydatkach, wielkością próby i ograniczeniami selekcji. Nie przypisuj przyczynowego efektu targetowania na podstawie samego podziału dostarczonej emisji.

- **Uzupełnienie 0.2 — decyzja o umiejscowieniach (METODA, inspiracja E01):** dla kandydata do ograniczenia przygotuj udział wydatków, koszt uzgodnionego wyniku, jego wolumen i jakość oraz podgląd reklamy w tym miejscu. Zdiagnozowana nieczytelność prowadzi najpierw do propozycji poprawy formatu. Trwałe przekroczenie uzgodnionego kosztu przy dojrzałych danych może uzasadniać test ograniczenia emisji; wynik oceniaj również łącznie dla kampanii.

## ST-01 — Cel biznesowy, zdarzenie optymalizacji i KPI

- **Podstawa:** METODA; M08 wspiera rozróżnienie wartości i wolumenu. **Teraz:** cel kampanii dostępny; zdarzenie zestawu i brief wymagają uzupełnienia.
- **Dane:** brief, cel kampanii, miejsce konwersji, zdarzenie/strategia optymalizacji, KPI klienta i jakość sygnału.
- **Sygnał:** firma potrzebuje kwalifikowanych zapytań lub sprzedaży, a konfiguracja i raport oceniają głównie kliknięcia albo wypełnienia bez dalszej kwalifikacji.
- **Postępowanie:** sprawdź zgodność całego łańcucha. W razie małego wolumenu głębokiego zdarzenia rozważ strukturę i jakość danych, a test zastępczego zdarzenia projektuj z oceną właściwego wyniku biznesowego.
- **Nie wnioskuj:** najtańszy klik jest najlepszym klientem; zmiana celu na płytszy tylko po to, aby poprawić status uczenia, jest automatycznie korzystna.
- **Ocena i wyjątki:** etap budowania zasięgu, test oferty lub kampania informacyjna może mieć odrębny KPI. Zapisz uzasadnienie; nie oceniaj jej tak samo jak kampanii bezpośredniej sprzedaży.

- **Uzupełnienie 0.2 — kontrola automatyzacji (METODA, M08; przegląd E01):** w notatce połącz KPI biznesowy z rzeczywistym zdarzeniem i celem optymalizacji zestawu. Przy rozbieżności przygotuj test właściwego zdarzenia i wymagania pomiaru. Meta opisuje optymalizację liczby i wartości konwersji; nie przypisuj systemowi celu kliknięć bez odczytu konfiguracji.

## ST-02 — Uproszczenie struktury z zachowaniem sensu biznesowego

- **Podstawa:** META M01/M02 — kierunek upraszczania; METODA — warunki i wyjątki. **Teraz:** wymaga danych zestawów i budżetów.
- **Dane:** struktura, powody podziału, budżety, zdarzenia, wolumen wyniku, rynki, oferty, ograniczenia i prowadzone testy.
- **Sygnał:** wiele podobnych zestawów z małym wolumenem, bez jasnego powodu rozdzielenia.
- **Postępowanie:** zaproponuj test konsolidacji jednostek o zgodnym celu i ekonomii. Przed scaleniem sprawdź, czy trzeba zachować kontrolę budżetu, rynku, produktu, harmonogramu lub eksperymentu.
- **Nie wnioskuj:** więcej zestawów zawsze szkodzi; wszystkie kampanie powinny trafić do jednej; podobna nazwa dowodzi nakładania się odbiorców.
- **Ocena i wyjątki:** oceniaj koszt i wolumen właściwego wyniku, a także utratę potrzebnej kontroli. Odmienne marże, języki, limity, kontrakty klienta i grupy kontrolne mogą uzasadniać podział.

## ST-03 — Uczenie i historia zmian

- **Podstawa:** META M07 — dostępność informacji o uczeniu; METODA — interpretacja. **Teraz:** wymaga dodatkowych odczytów.
- **Dane:** status uczenia zestawu, czas ostatniej istotnej edycji, historia budżetu/stawek/kreacji, wolumen zdarzenia i dojrzałość wyników.
- **Sygnał:** wynik zmienia się po edycji, a kolejne zmiany utrudniają ustalenie punktu odniesienia.
- **Postępowanie:** nanieś zmiany na oś czasu. Oddziel okresy konfiguracji i oceń, czy kolejna interwencja jest uzasadniona. Grupuj planowane zmiany tylko wtedy, gdy nie uniemożliwi to odpowiedzi na pytanie testu.
- **Nie wnioskuj:** zawsze czekamy dokładnie siedem dni; stały próg zdarzeń gwarantuje sukces; każdy procent podwyżki działa tak samo; wyjście z uczenia dowodzi rentowności.
- **Ocena i wyjątki:** ustal horyzont z uwzględnieniem opóźnienia i ryzyka, nie uniwersalnej liczby. Potwierdzony błąd konfiguracji lub przekroczenie uzgodnionego limitu może wymagać interwencji przed końcem obserwacji.

## CR-01 — Różnorodność koncepcji i zgodność z ofertą

- **Podstawa:** META M03 — kierunek różnicowania; METODA — taksonomia i kontrola; HIPOTEZA — wpływ konkretnej koncepcji. **Teraz:** brak treści i wyników reklam.
- **Dane:** materiały reklamowe, komunikat, oferta/strona docelowa, format i umiejscowienie, daty uruchomienia, dane na poziomie reklamy oraz opis odbiorcy.
- **Sygnał:** wiele wariantów zmienia tylko kolor lub pierwsze słowo; brakuje odmiennych argumentów, dowodów i sposobów pokazania oferty; reklama obiecuje coś innego niż strona.
- **Postępowanie:** oznacz koncepcję, potrzebę odbiorcy, obietnicę, dowód, format, otwarcie i CTA. Oddziel test nowej koncepcji od wariantu wykonania. Zaproponuj brakującą hipotezę i materiał dostosowany do miejsca emisji.
- **Nie wnioskuj:** więcej plików równa się większa różnorodność; wysoki CTR oznacza najlepszą sprzedaż; brak wydatków dowodzi słabości kreacji; wideo lub treść twórcy zawsze wygrywa.
- **Ocena i wyjątki:** mierz właściwy wynik, koszt przygotowania i sensowną ekspozycję. Przy małym budżecie testuj mniej koncepcji jednocześnie; nie ustalamy uniwersalnej liczby reklam.

- **Uzupełnienie 0.2 — automatyczne warianty (METODA, inspiracja E01):** odczytaj dostępne ustawienia modyfikacji obrazu i tekstu, sprawdź podglądy oraz zgodność obietnicy z ofertą. Każdą poprawkę przypisz do konkretnego elementu. Gdy wynik jest dostępny tylko dla całej reklamy, zaprojektuj osobny test elementu zamiast przypisywać mu wynik zestawu wariantów.

## CR-02 — Hipoteza zużycia kreacji

- **Podstawa:** METODA + HIPOTEZA; bez uniwersalnego progu Mety. **Teraz:** brak danych reklam i zasięgu za cały okres.
- **Dane:** trend tej samej kreacji, ekspozycja, częstotliwość w spójnym oknie, zasięg, CTR, wynik biznesowy, CPM, zmiany oferty i odbiorców.
- **Sygnał:** powtarzająca się ekspozycja towarzyszy pogorszeniu reakcji i wyniku po uwzględnieniu kosztu dotarcia i innych zmian.
- **Postępowanie:** przedstaw zużycie jako jedno z wyjaśnień; porównaj z sezonowością, zmianą miksu i problemami po kliknięciu. Zaprojektuj test odświeżenia koncepcji przy możliwie porównywalnych warunkach.
- **Nie wnioskuj:** frequency > 3, wiek 11 dni lub sam spadek CTR dowodzi zużycia; kreacje trzeba wymieniać według jednego kalendarza.
- **Ocena i wyjątki:** oceń wynik biznesowy nowego wariantu, nie tylko tanią uwagę. Remarketing, małe grupy, długi proces zakupu i kampanie zasięgowe mogą wymagać innej interpretacji ekspozycji.

## AU-01 — Automatyzacja, odbiorcy i umiejscowienia

- **Podstawa:** META M01 — automatyzacja jako kierunek; METODA + HIPOTEZA — sposób testu. **Teraz:** wymaga ustawień zestawów, podziałów i zgodności formatu.
- **Dane:** realne ograniczenia dostawy/usługi, rynek, język, marka, ustawienia odbiorców i umiejscowień, materiały, wynik biznesowy oraz dostępne opcje na koncie.
- **Sygnał:** liczne ręczne ograniczenia bez uzasadnienia albo automatyzacja nieuwzględniająca ograniczeń biznesu.
- **Postępowanie:** przygotuj test szerszej dystrybucji albo uzasadnionego ograniczenia w granicach klienta, zależnie od rozpoznanego problemu. Rozróżnij sugestie dla systemu od twardych ograniczeń konkretnej funkcji; sprawdź je przed planem wdrożenia.
- **Nie wnioskuj:** szeroka grupa zawsze wygra; rekomendacja platformy jest poleceniem; tani placement można oceniać bez jakości wyniku; wolno przekroczyć obszar obsługi dla niższego CPL.
- **Ocena i wyjątki:** porównaj wolumen, koszt i jakość w poprawnie zaplanowanym teście. Uzasadnione ograniczenia marki, rynku i dostępności oferty pozostają warunkami testu.

- **Uzupełnienie 0.2 — wybór wariantu odbiorców (METODA + HIPOTEZA, inspiracja E01):** porównaj obecną konfigurację z jednym wariantem odpowiadającym problemowi: szerszą dystrybucją, ograniczeniem wynikającym z obszaru obsługi albo sygnałem z aktualnych danych klientów. Dobór listy oprzyj na jakości i wartości klientów, jej zakresie i świeżości. Zweryfikuj, czy lista działa jako sugestia czy ograniczenie; dopiero wtedy nazwij zakres remarketingowym. Zapisz co zmieniasz, co zachowujesz i czy celem oceny jest koszt kwalifikowanego leada, zakupu czy nowego klienta.

## LD-01 — Jakość leadów i cały proces sprzedaży

- **Podstawa:** METODA; M05 częściowo potwierdza kierunek użycia sygnału CRM. **Teraz:** brak mapowania i integracji CRM.
- **Dane:** leady, duplikaty/spam, definicja kwalifikacji, kontakt, spotkanie/oferta, sprzedaż, wartość i terminy etapów, czas reakcji handlowców; spójne kohorty i zakres kosztów.
- **Sygnał:** tani CPL przy niskiej kwalifikacji; spadek sprzedaży mimo stałego napływu; różnice jakości między ofertami/formularzami.
- **Postępowanie:** policz osobno CPL, CPQL, koszt sprzedaży i przejścia etapów. Rozdziel jakość pozyskania od jakości i czasu obsługi. Porównuj kohorty o podobnej dojrzałości; zgodnie ze źródłem ogranicz zakres wniosków.
- **Nie wnioskuj:** formularze natywne dają zawsze gorszą jakość; najwyższy CPL jest najgorszy; nowe leady bez zamkniętej sprzedaży są bezwartościowe; wszystkie leady z CRM pochodzą z Meta.
- **Ocena i wyjątki:** wygrywa uzgodniony wynik biznesowy przy dopuszczalnym wolumenie, nie automatycznie najniższy CPL. Przykład CPQL i definicje znajdują się w metodach. System ma używać agregatów, nie danych kontaktowych osób.

## EC-01 — Sprzedaż, marża i nowi klienci

- **Podstawa:** METODA; M08 rozróżnia wartość od wolumenu. **Teraz:** brak mapowania i danych sklepu.
- **Dane:** zakupy, wartość i waluta, opłacenie/anulowanie/zwrot, marża przed reklamą, koszty zmienne, nowi/powracający klienci, dostępność towaru; zakres atrybucji.
- **Sygnał:** dobry ROAS przy niskiej marży, wysokich zwrotach lub dominacji powracających klientów; wynik rośnie dzięki produktom o innej ekonomii.
- **Postępowanie:** pokaż raportowany ROAS obok wyniku po uzgodnionych kosztach i, jeśli dane pozwalają, kosztu nowego klienta. Podaj założenia progu opłacalności i horyzont LTV.
- **Nie wnioskuj:** ROAS 3 zawsze oznacza zysk; każdy zakup to nowy klient; przychód przypisany reklamie jest w całości przyrostowy; wysoki LTV usprawiedliwia dowolny koszt dziś.
- **Ocena i wyjątki:** oceń marżę po reklamie, płynność i wolumen zgodnie z celem. Pozyskiwanie klientów może mieć celowo inny horyzont zwrotu, ale wymaga jawnego limitu i uzgodnienia ekonomii.

## EX-01 — Testy A/B i ranking obserwacyjny

- **Podstawa:** META M04 — narzędzia eksperymentu; METODA — protokół oceny. **Teraz:** planowanie; brak odczytu eksperymentów.
- **Dane:** pytanie, warianty, jednostka i sposób losowania, wspólne warunki, metryka główna, planowana próba/horyzont, kryteria przerwania i wynik testu.
- **Sygnał:** ktoś ogłasza zwycięzcę po kilku wynikach albo porównuje reklamy o nierównej ekspozycji jak kontrolowany eksperyment.
- **Postępowanie:** odróżnij ranking historyczny od testu. Zmieniaj jedną interpretowalną zmienną albo testuj pakiet jako całość. Ustal analizę przed startem; przy metodzie sekwencyjnej zastosuj właściwą kontrolę błędów zamiast arbitralnego codziennego kończenia testu.
- **Nie wnioskuj:** kilka reklam w jednym zestawie to automatycznie losowy test; niskie wydatki wariantu dowodzą jego słabości; test całego pakietu identyfikuje efekt każdej składowej.
- **Ocena i wyjątki:** raportuj efekt, niepewność, dojrzałość i odstępstwa od planu. Przy braku odpowiedniej próby dopuszczalny jest wynik nierozstrzygający lub eksploracja bez twierdzeń przyczynowych.

- **Uzupełnienie 0.2 — porównanie ustawień (METODA, M04; przegląd E01):** przygotuj jeden test odpowiadający na konkretną decyzję o budżecie, odbiorcach, umiejscowieniu lub kreacji. Równe kwoty, osobne zestawy i ręczna rotacja nie zapewniają losowego podziału odbiorców. Bez takiego podziału zapisz porównanie jako eksploracyjne; nie przedstawiaj go jako kontrolowanego A/B.

## EX-02 — Atrybucja a wynik przyrostowy

- **Podstawa:** META M04 — Conversion Lift; METODA — rozróżnienie pytań pomiarowych. **Teraz:** brak eksperymentów przyrostowych.
- **Dane:** wynik przypisany przez platformę, sprzedaż biznesowa, inne kanały, ekspozycja lub grupa kontrolna, projekt testu i zakłócenia.
- **Sygnał:** wysoki ROAS remarketingu traktowany jako dowód dodatkowej sprzedaży; wzrost sprzedaży po zmianie utożsamiany z jej efektem.
- **Postępowanie:** nazwij oddzielnie wynik przypisany i efekt względem sytuacji bez interwencji. Gdy decyzja uzasadnia koszt badania, zaproponuj Conversion Lift lub poprawnie zaprojektowany holdout. Dostępność narzędzia należy sprawdzić na koncie.
- **Nie wnioskuj:** suma konwersji przypisanych przez kilka platform równa się sprzedaży; porównanie przed/po izoluje wpływ reklamy; etykieta modelowanej atrybucji zastępuje ocenę jakości eksperymentu.
- **Ocena i wyjątki:** wynik przyrostowy raportuj wraz z niepewnością i zakresem badania. Mały budżet może uzasadniać analizę opisową, która nie udaje eksperymentu.

## OP-01 — Skalowanie z kontrolą jakości i ryzyka

- **Podstawa:** METODA + HIPOTEZA. **Teraz:** planowanie; brak wykonawcy zmian i wymaganych danych.
- **Dane:** dojrzałe wyniki, aktualne budżety i stawki, historia zmian, cele kosztu/wartości, limit ryzyka, marża lub jakość leadów oraz zdolność obsługi.
- **Sygnał:** wynik spełnia uzgodnione cele przy istotnym wolumenie i jest biznesowa potrzeba wzrostu.
- **Postępowanie:** przygotuj konkretny test ze stanem przed/po, maksymalnym dodatkowym wydatkiem, okresem oceny i metrykami ochronnymi. Obserwuj zmianę kosztu i jakości przy zwiększaniu skali. Historyczna relacja dodatkowego kosztu do dodatkowego wyniku jest opisowa, jeśli nie ma kontrolowanego testu.
- **Nie wnioskuj:** podwojenie budżetu podwoi sprzedaż; dobry średni CPA oznacza taki sam koszt kolejnego klienta; stałe +20% jest bezpieczne dla każdego konta.
- **Ocena i wyjątki:** jakość, marża, wolumen i ograniczenia operacyjne muszą pozostać akceptowalne. Brak towaru, przeciążenie handlowców lub brak wiarygodnego pomiaru może uzasadniać brak skalowania mimo dobrego raportu.

## PL-01 — Spójny brief przed utworzeniem kampanii

- **Podstawa:** METODA. **Teraz:** lokalny kontrakt briefu; brak pełnej walidacji zasobów i tworzenia kampanii.
- **Dane:** cel, oferta, odbiorca, rynek, zdarzenie i miejsce konwersji, KPI, budżet/termin, strona/formularz, materiały, ograniczenia marki i plan testu.
- **Sygnał:** próba uruchomienia bez definicji sukcesu albo niespójna obietnica, cel optymalizacji i miejsce docelowe.
- **Postępowanie:** sprawdź łańcuch oferta → komunikat → strona/formularz → zdarzenie → KPI → obsługa wyniku. Zapisz brakujące dane, hipotezę kampanii i kryterium oceny. Specyfikacje formatów i dostępność funkcji sprawdź w aktualnych źródłach przed wykonaniem planu.
- **Nie wnioskuj:** pomyślna walidacja JSON oznacza gotowość konta, zatwierdzenie reklamy lub możliwość automatycznej publikacji. Kompendium nie zastępuje procedur uprawnień i wykonania.
- **Ocena i wyjątki:** można przygotować koncepcję z brakującymi informacjami, jeśli są nazwane. Gotowość do publikacji wymaga osobnej walidacji i upoważnienia w ramach wdrożonego wykonawcy.
