# Przegląd E01: kontrola automatyzacji

- Wersja notatki: 0.1; data: 2026-09-10; wydanie kompendium: 0.2.
- Źródło i autor materiału: [E01 — Jan Wojciechowski, Marketing Online](../sources.md#e01).
- Opracowanie: agent projektu na polecenie użytkownika. Recenzent specjalistyczny: brak; `expert_review: pending`.
- Rodzaj wkładu: zewnętrzna heurystyka, przekształcona w warunkowe procedury analityczne. Status zmienionych kart: `guidance`.
- Zakres: kampanie sprzedażowe i leadowe; budżet, odbiorcy, umiejscowienia oraz kreacje. Parametry liczbowe: brak nowych wartości domyślnych.

## Decyzje redakcyjne

Rozszerzono sześć istniejących kart, zachowując ich dane wejściowe, wyjątki i ocenę rezultatu. Procedury wymagają konkretnego problemu na koncie i prowadzą do propozycji działania albo testu. Nie tworzymy drugiego zestawu równoległych reguł.

Rozstrzygnięcia projektu:

- ST-02 zachowuje zasadę konsolidacji tam, gdzie podział nie ma uzasadnienia. PE-03 dopuszcza osobny budżet, gdy wymaga go eksperyment lub priorytet biznesowy.
- AU-01 dobiera kierunek zmiany do problemu; szerokość odbiorców i źródło listy są parametrami testu.
- ST-01 wymaga odczytu celu optymalizacji. [M08](../sources.md#m08) opisuje cele związane z konwersjami i ich wartością.
- EX-01 zachowuje wymóg losowania dla kontrolowanego A/B. [M04](../sources.md#m04) potwierdza dostępność materiałów o eksperymentach; szczegółowy protokół pozostaje metodą projektu.
- Każdy zapis wymaga akceptacji konkretnego planu; kasowanie jest zabronione, również podczas optymalizacji kreacji.

## Weryfikacja i wykorzystanie

Ponownie odczytano publiczne materiały M04 i M08. Próba sprawdzenia dokumentacji odbiorców pod adresem `https://www.facebook.com/business/help/273363992030035` prowadziła do logowania. Nie potwierdzono na tej podstawie aktualnych przełączników ani dostępności opcji; należy je odczytać na koncie przed przygotowaniem konkretnej zmiany.

Scenariusze CASE-17–22 obejmują zastosowanie i kontrprzypadki. Są materiałem do przyszłej oceny zachowania agenta, nie wykonanym testem kampanii. Sprawdzono redakcyjnie zgodność kart, źródeł i zasad akceptacji. Nie zmieniono silnika obliczeń ani ustawień kont.

Przy analizie agent zapisuje zastosowaną kartę i warunki w notatce. Użytkownik otrzymuje rekomendację, dane uzasadniające działanie i sposób oceny efektu, zgodnie ze [standardem analiz](../../../docs/analysis-standard.md).
