# Model danych v0.1

## Obiekty i relacje

| Obiekt | Najważniejsze pola i reguły |
| --- | --- |
| `Client` | `client_id`, nazwa, status; bez sekretów |
| `CredentialRef` | Identyfikator magazynu/zmiennej, właściciel i zakres; bez wartości tokena |
| `AdAccount` | `client_id`, `account_id`, referencja poświadczeń, waluta, strefa czasowa, wynik kontroli dostępu |
| `BusinessProject` | Projekt klienta, przypisane konta, oferta, rynek i wytyczne marki |
| `GoalProfile` | Projekt, typ `lead_generation` lub `ecommerce`, zdarzenie wyniku, metryki i cele |
| `CampaignBinding` | Powiązanie kampanii z projektem i profilem celu; brak powiązania blokuje ocenę względem celu |
| `Policy` | Wersja zasad wykonania, limity zmian, dozwolone działania i tryb |
| `ObjectSnapshot` | Konto, identyfikator i typ obiektu Meta, pola konfiguracji, czas odczytu, wersja API |
| `InsightFact` | Konto, poziom obiektu, okres, wymiary, specyfikacja raportu, miary i czas pobrania |
| `AnalysisRun` | Wersja procedury i kodu, dane wejściowe, wynik kontroli jakości i identyfikatory dowodów |
| `Recommendation` | Obserwacja, hipoteza, dowody, proponowane działanie, ograniczenia i termin oceny |
| `ChangePlan` | Zakres, operacje, warunki wstępne, wersja polityki, hash, ważność |
| `Authorization` | Osoba lub polityka upoważniająca, hash planu, zakres i czas ważności |
| `Execution` | Plan, operacje, próby, wyniki, błędy, wartości przed i po |

Identyfikatory Meta są ciągami znaków. Powiązania w bazie muszą uniemożliwiać przypisanie obiektu do konta innego klienta. W MVP konto jest przypisane do jednego klienta; jego przeniesienie jest jawną operacją administracyjną poza zwykłą synchronizacją.

## Kontekst biznesowy

Klient może mieć jednocześnie profil leadowy i sprzedażowy. Cele są wersjonowane z datą obowiązywania; zmiana docelowego CPA dzisiaj nie zmienia historycznej oceny raportów. Cele biznesowe i ograniczenia wykonawcze są osobnymi obiektami.

Profil leadowy określa zdarzenie leada, definicję leada kwalifikowanego, docelowy CPL/CPQL oraz źródło danych o sprzedaży. Profil e-commerce określa zdarzenie zakupu, docelowy CPA/ROAS i — jeśli dane istnieją — sposób liczenia marży oraz zwrotów.

Brak danych z CRM lub sklepu daje `unavailable`, nie zero. Bez informacji o jakości leadów raport nie ocenia jakości. Raportowany ROAS Mety nie jest utożsamiany z rentownością firmy ani przychodem inkrementalnym.

## Raporty i metryki

Każdy zestaw wyników przechowuje:

- przedział dat w strefie konta, poziom agregacji i wymiary podziału;
- walutę oraz identyfikatory konta, obiektu i klienta;
- żądane i efektywne ustawienia atrybucji, jeśli API je udostępnia;
- sposób przypisania działań do daty, zdarzenie konwersji i definicję kliknięcia;
- wersję API, parametry raportu, czas pobrania i status kompletności;
- wersję normalizacji i referencję do zredagowanego źródła.

Klucz faktu obejmuje zakres klienta/konta, obiekt, okres, wymiary i sygnaturę specyfikacji raportu. Raportów z różnymi ustawieniami atrybucji lub podziałami nie łączymy automatycznie.

Miary pieniężne przechowujemy jako wartości dziesiętne, a w JSON jako tekst. Konwersje nie muszą być całkowite. Jednostka pola budżetowego jest interpretowana zgodnie z kontraktem danego endpointu i walutą; nie zakładamy globalnie mnożnika 100.

| Metryka | Definicja |
| --- | --- |
| CPM | `spend / impressions * 1000` |
| CTR | `wybrany_typ_kliknięć / impressions`; raport wskazuje typ kliknięcia |
| CPC | `spend / wybrany_typ_kliknięć` |
| CPA / CPL | `spend / liczba_wskazanych_konwersji` |
| ROAS | `wartość_wskazanych_zakupów / spend` |
| CPQL | `spend / qualified_leads`; tylko przy dostępnej, zgodnej definicji danych CRM |

Przy mianowniku równym zero zwracamy `null` i powód. Wskaźniki agregujemy ponownym obliczeniem z sum składowych, nie średnią ze wskaźników. Reach i frequency nie są addytywne: pobieramy je na docelowym poziomie raportu lub oznaczamy brak możliwości agregacji. Nie sumujemy alternatywnych typów akcji opisujących tę samą konwersję.

## Synchronizacja i kontrola jakości

Pobieramy pełną strukturę oraz historię według wskazanego zakresu. Kolejne synchronizacje są przyrostowe, ale ponownie pobierają ruchome okno ostatnich dni. Jego długość zależy od używanej atrybucji i opóźnień; dostępny jest również ponowny import starszego okresu.

Ponowne pobranie tworzy nową wersję snapshotu. Raport już zapisany odwołuje się do wersji danych użytej przy obliczeniu. Synchronizacja ma stan `PENDING`, `RUNNING`, `SUCCEEDED`, `PARTIAL` lub `FAILED`; przerwanie w połowie nie może zostać przedstawione jako pełny raport.

Kontrole obejmują kompletność stron i dni, aktualność danych, brakujące zdarzenia, zgodność waluty i atrybucji, porównywalność okresów oraz liczebność próby. Niedostępny podział nie jest pustym segmentem. Bieżący niepełny dzień jest oznaczany i domyślnie wyłączany z porównań pełnych dni.

## Wnioski i historia efektów

Każda rekomendacja ma identyfikatory dowodów, zakres dat, opis niepewności i warunki unieważniające hipotezę. Po wykonaniu zmiany zapisujemy termin oceny oraz inne zmiany, które zaszły w międzyczasie.

Porównanie przed/po jest opisowe. Nie dowodzi przyczynowości. Test kontrolowany wymaga osobnego projektu eksperymentu. Domyślnie nie zapisujemy w MVP danych osobowych leadów; przyszła integracja CRM zaczyna od agregatów i jawnej definicji łączenia danych.

Historia operacji jest dopisywana, a nie nadpisywana przez kolejną próbę. Retencja danych i plików źródłowych będzie konfigurowalna; lokalna baza i raporty nie trafiają do repozytorium.
