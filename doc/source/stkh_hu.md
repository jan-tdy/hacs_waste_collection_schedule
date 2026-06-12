# STKH

Support for waste collection schedules provided by [STKH](https://stkh.hu/), serving municipalities in Győr-Moson-Sopron county, Hungary.

## Configuration via configuration.yaml

```yaml
waste_collection_schedule:
    sources:
      - name: stkh_hu
        args:
          settlement: SETTLEMENT_NAME
          postcode: POSTCODE
```

### Configuration Variables

**settlement**
*(string) (required)*
Settlement name (e.g., Újkér, Und)

**postcode**
*(string) (required)*
Postcode of the settlement (e.g., 9472, 9464)

## Example

```yaml
waste_collection_schedule:
    sources:
      - name: stkh_hu
        args:
          settlement: "Újkér"
          postcode: "9472"
```

## How to get the source arguments

Visit the [STKH schedule page](https://stkh.hu/hulladeknaptar/) and find your settlement. Enter the settlement name and postcode as shown on the website.
