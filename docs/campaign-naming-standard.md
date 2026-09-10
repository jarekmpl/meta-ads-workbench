# Proponowany standard nazw kampanii, zestawów i reklam

Wersja **1.0, 2026-09-10**, do wdrożenia w generatorze planów. Standard dotyczy nowych obiektów. Nie zmienia nazw istniejących kampanii i nie upoważnia do zapisów w Meta.

## Co zapisujemy w nazwie

Nazwa ma pomagać operatorowi rozpoznać obiekt. Pełną konfigurację przechowujemy w planie i rejestrze, a wyniki łączymy po identyfikatorach. Nie wyciągamy celu, grupy odbiorców ani budżetu wyłącznie z nazwy.

Przed planowaniem klient otrzymuje stały, krótki kod, a projekt kod oferty, produktu lub wydarzenia. Kody uzgadniamy raz i zapisujemy w profilu. W nazwach stosujemy wielkie litery ASCII, cyfry, łącznik wewnątrz pola i separator ` | ` pomiędzy polami. Generator usuwa polskie znaki z kodów, ale pełne opisy w raporcie pozostają po polsku.

Lokalne klucze `C0001`, `S0001`, `A0001` identyfikują planowane kampanie, zestawy i reklamy. Liczniki są osobne dla typu obiektu i konta, nie resetują się przy nowym projekcie i mogą przekroczyć cztery cyfry. Generator rezerwuje je atomowo; wznowienie planu zachowuje rezerwacje. Pełnym kluczem jest para konto–klucz. Po utworzeniu obiektu zapisujemy powiązanie z ID Meta. Numer wersji tekstu lub materiału nie zastępuje ID obiektu.

## Wzorce

| Poziom | Wzorzec | Znaczenie |
| --- | --- | --- |
| Kampania | `KLIENT | PROJEKT | CEL | RYNEK-JEZYK | ROLA | C0001` | Cel to wynik biznesowy; rola opisuje przeznaczenie kampanii |
| Zestaw | `C0001 | POMIAR | MIEJSCE | GRUPA | OBSZAR | S0001` | Wskazuje kampanię nadrzędną, wynik mierzony i założenia dystrybucji |
| Reklama | `S0001 | KONCEPCJA | FORMAT | WERSJA | A0001` | Wskazuje zestaw, pomysł reklamowy, wykonanie i wersję |

Proponowany słownik:

- Cel: `LEAD`, `SALE`, `REG`. Sprzedaż biletów to `SALE`, nawet gdy pomiar obejmuje wcześniejsze działanie.
- Rola: `MAIN` dla kampanii podstawowej, `TEST` dla osobnego testu, `RET` dla wydzielonego remarketingu. Te role nie nakazują utworzenia trzech kampanii.
- Pomiar: `LEAD`, `PURCHASE`, `REG-CONF` dla potwierdzonej rejestracji, `OUTCLICK` dla uzgodnionego przekliknięcia do zakupu. To etykiety biznesowe, a nie nazwy zdarzeń API. Dokładne mapowanie zdarzenia i cel optymalizacji są osobnymi polami planu.
- Miejsce konwersji lub zdarzenia: `FORM` albo `WEB`.
- Grupa: `BROAD`, `CRM-SUG`, `CRM-ONLY`, `RET-SUG`, `RET-ONLY`, `CUSTOM`. Końcówka `SUG` oznacza sugestię odbiorców; `ONLY` wolno nadać dopiero po potwierdzeniu faktycznych ograniczeń emisji. Szczegóły należą do konfiguracji.
- Rynek i język: np. `PL-PL`, `DE-DE`; wiele rynków oznaczamy `MULTI` i opisujemy w planie. Obszar zestawu to np. `PL` lub kod regionu z rejestru projektu.
- Format: `IMG-1X1`, `IMG-9X16`, `VID-9X16`, `CAR`, `MULTI`. `MULTI` obejmuje kilka adaptacji w jednej reklamie. Format nazwy musi odpowiadać przygotowanym materiałom.
- Wersja: `V01`, `V02` itd. Każda zmiana tekstu lub materiału tworzy nową wersję lokalnego pakietu. Jeżeli powstaje nowa reklama, otrzymuje też nowy klucz `A`.

Nowe kody dopisujemy do wersjonowanego słownika z opisem. Nie pozwalamy agentowi tworzyć różnych skrótów tego samego pojęcia w kolejnych rozmowach. W podsumowaniu rozwijamy skróty, np. „sprzedaż biletów; pomiar kliknięcia do operatora”.

## Przykłady fikcyjne

| Wariant | Kampania | Zestaw | Reklama |
| --- | --- | --- | --- |
| Leady dla usługi | `DEMO | KONSULTACJA | LEAD | PL-PL | MAIN | C0001` | `C0001 | LEAD | FORM | BROAD | PL | S0001` | `S0001 | PRZEBIEG-USLUGI | IMG-1X1 | V01 | A0001` |
| Sklep | `DEMO | KOLEKCJA | SALE | PL-PL | MAIN | C0002` | `C0002 | PURCHASE | WEB | BROAD | PL | S0002` | `S0002 | ZASTOSOWANIE | VID-9X16 | V01 | A0002` |
| Zapisy | `DEMO | WEBINAR | REG | PL-PL | MAIN | C0003` | `C0003 | REG-CONF | WEB | BROAD | PL | S0003` | `S0003 | PROGRAM | IMG-1X1 | V01 | A0003` |
| Bilety, pomiar kliknięcia do operatora | `DEMO | WYDARZENIE | SALE | PL-PL | MAIN | C0004` | `C0004 | OUTCLICK | WEB | BROAD | PL | S0004` | `S0004 | PRELEGENCI | VID-9X16 | V01 | A0004` |

Przykłady pokazują zapis nazw, nie gotowe ustawienia ani rekomendowaną liczbę obiektów. W ostatnim wariancie cel biznesowy to sprzedaż, a dostępny pomiar to przekliknięcie. Możliwość optymalizacji na to zdarzenie wymaga sprawdzenia.

## Stabilność i kontrola

Nie umieszczamy w nazwach aktualnego budżetu, CPA, statusu ani bieżącej daty raportu. Termin może być częścią stałego kodu projektu, jeśli rozróżnia edycje wydarzenia, np. `KONFERENCJA-2026`. Nie stosujemy danych osobowych ani informacji poufnych.

Przed pierwszym zapisem generator sprawdza kolejność i liczbę pól, znaki, słownik, przypisanie rodzica oraz unikalność nazwy w danym typie obiektu i koncie. Docelowy limit długości sprawdza według obsługiwanej wersji API. Zbyt długie opisy zamienia na krótsze, zarejestrowane kody z zachowaniem klucza; nie ucina nazwy bez sprawdzenia kolizji.

Istniejące nazwy można przypisać do metadanych projektu lokalnie. Zmiana nazwy w Meta wymaga zatwierdzonego planu. Historia rejestru zachowuje stare i nowe nazwy, wersje konfiguracji oraz identyfikatory. Adresy UTM i raporty powinny korzystać ze stabilnego mapowania identyfikatorów, zamiast polegać na rozbieraniu nazw na części.
