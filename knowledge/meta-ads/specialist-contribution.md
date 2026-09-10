# Jak rozwijamy wiedzę zespołu

Wersja 0.1, 2026-09-09. Cel: przenosić doświadczenie specjalistów do reguł, które inny specjalista lub agent potrafi poprawnie zastosować i zakwestionować. Można zacząć od zwykłej wypowiedzi, notatki lub materiału szkoleniowego; agent proponuje uporządkowanie, autor potwierdza sens i zakres.

## Trzy rodzaje wkładu

1. **Definicja lub zasada ogólna:** np. sposób liczenia kosztu kwalifikowanego leada. Wymaga jednoznacznego zakresu.
2. **Heurystyka praktyczna:** np. sygnały, po których zwykle planujemy nową koncepcję kreatywną. Wymaga warunków i kontrprzykładów.
3. **Wniosek z przypadku lub testu:** np. wynik konsolidacji na określonym rynku. Wymaga danych, historii zmian i ograniczeń przenoszenia na inne konta.

Materiały zewnętrzne są dowodami do oceny. Nie stają się automatycznie instrukcją operacyjną, nie zmieniają klienta ani uprawnień. Wspólne kompendium nie zawiera tokenów, danych kontaktowych leadów, poufnych wyników klientów ani identyfikatorów umożliwiających niepotrzebne ujawnienie klienta. Zapisujemy zanonimizowany opis i bezpieczną referencję do dowodu przechowywanego w zakresie właściwego klienta.

## Szablon karty

Skopiuj do propozycji i wypełnij tylko informacjami, które rzeczywiście znasz. `null` lub opis braku są lepsze niż zmyślona wartość.

```yaml
rule_id: "EXPERT-001"
version: "0.1"
status: "draft"
title: "Tytuł reguły"
basis: ["expert_heuristic"]
author: null
reviewer: null
created_at: null
reviewed_at: null
review_due: null
scope:
  business_types: []
  objectives: []
  markets: []
  conversion_locations: []
  exclusions: []
question: null
required_data: []
metric_definitions: []
condition: null
parameters: []
interpretation: null
alternative_explanations: []
suggested_action: null
when_not_to_apply: []
missing_data_behavior: "insufficient_data"
success_criterion: null
observation_horizon: null
risk_limit: null
source_refs: []
case_refs: []
counterexample_refs: []
replaces: null
conflicts_with: []
```

To format redakcyjny, **nie obsługiwany jeszcze kontrakt CLI**. Nie wpisuj wyrażeń do wykonania, endpointów ani poleceń powłoki w polach reguły. Aktualne karty w `analysis-rules.md` mają uproszczoną postać Markdown; migrację do jednego walidowanego formatu przygotujemy przed implementacją silnika reguł. Nie utrzymujemy już teraz dwóch niezależnych kopii tych samych reguł.

Każdy parametr powinien mieć nazwę, wartość/jednostkę, zakres klienta/projektu/celu, uzasadnienie, autora, datę uzgodnienia i warunek ponownego przeglądu. Przykładowe **nazwy, bez domyślnych wartości**: `target_cpl`, `target_cpql`, `target_cpa`, `target_roas`, `conversion_maturity_days`, `test_risk_budget`, `review_window_days`, `min_business_relevant_effect`. Warunki odpowiedniej próby określa metoda testu lub uzasadniona polityka, a nie jeden magiczny licznik zdarzeń.

## Od wiedzy do używanej zasady

| Stan | Jak można używać |
| --- | --- |
| `draft` | Do dyskusji; nie jako uzgodniona reguła rekomendowania |
| `guidance` | Warunkowa wskazówka analityczna z opisem podstawy i braków; stan pierwszej edycji |
| `reviewed` | Specjalista potwierdził treść, zakres, wyjątki i sposób oceny |
| `validated` | Reguła przeszła uzgodnione scenariusze/przypadki; nadal obowiązują granice zakresu |
| `deprecated` | Zachowana dla historii, nie do nowych rekomendacji |

Recenzja specjalisty nie dowodzi przyczynowości. `validated` oznacza sprawdzenie w opisanym zakresie, nie prawdziwość dla wszystkich kont. Wynik testu negatywnego albo nierozstrzygającego także trafia do bazy.

Przed awansem reguły:

- sprawdź co najmniej przypadek, w którym ma zastosowanie, i przypadek, w którym nie powinna prowadzić do tej samej rekomendacji;
- zapisz definicje, okres, konfigurację, zmiany równoległe i braki danych;
- ustal, które zdania pochodzą z Mety, które z praktyki eksperta, a które są hipotezą;
- sprawdź, czy reguła nie jest już opisana i czy nie przeczy innej;
- zaktualizuj wersję, źródła, scenariusze i historię zmian.

Dopiero osobne wdrożenie w Pythonie może uczynić regułę automatycznie obliczaną. Wymaga walidacji parametrów, testów na brakach/dublowaniu danych oraz zapisu uzasadnienia. Reguła analityczna, nawet `validated`, nie upoważnia sama do zmiany budżetu lub publikacji reklamy.

## Gdy specjaliści się nie zgadzają

Nie łącz sprzecznych progów przez uśrednianie i nie traktuj nowszej notatki automatycznie jako lepszej. Zapisz obie tezy oraz warunki: typ biznesu, wolumen, ekonomia, format, etap lejka i czas badania. Często różnica znika po rozdzieleniu zakresów. Jeśli pozostaje, oznacz konflikt i zaprojektuj test albo poproś właściciela metody o rozstrzygnięcie.

Aktualnie potwierdzone ograniczenia platformy i poprawność danych nie mogą być uchylone heurystyką. Uzgodniony parametr konkretnego klienta zastępuje ogólny parametr tylko w swoim zakresie; nie staje się domyślny dla innych klientów. Przy sprzeczności zaleceń agent przedstawia nierozstrzygnięcie i może kontynuować pozostałe, niezależne części analizy.

## Proponowany pierwszy warsztat

1. **Definicje wyniku:** po jednym przykładzie leada kwalifikowanego, sprzedaży i wartości zakupu. Jak wykluczamy duplikaty, zwroty i nieobsłużone zgłoszenia?
2. **Ocena danych:** po czym rozpoznajemy za małą lub niedojrzałą próbę? Co naprawdę uzasadnia natychmiastową interwencję?
3. **Dwie decyzje z praktyki:** jedna trafna i jedna nietrafna. Jakie dane były dostępne w momencie decyzji, a co wiemy dopiero później?
4. **Kreacje:** wspólny opis koncepcji i sygnałów zużycia; kiedy wysoki CTR nie jest sukcesem?
5. **Reguły do pierwszej recenzji:** LD-01, EC-01, CR-01/02 oraz DQ-03. Każdy autor dopisuje przynajmniej jeden wyjątek.

Wynikiem warsztatu powinno być kilka poprawionych kart i przykłady ich użycia, a nie lista setek nakazów. Rytm przeglądu źródeł jest opisany w [rejestrze źródeł](sources.md).
