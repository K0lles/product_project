from typing import Type

from django.db.models import F, Model, OuterRef, Q, Subquery

from products.enums import ComparisonModelEnum


class BaseAggregator:
    comparison_model_enum: ComparisonModelEnum = ComparisonModelEnum

    def __init__(self, fields: dict[Type[Model], dict[str, tuple]]) -> None:

        self.fields: dict[Type[Model], dict[str, tuple]] = fields

        self.annotations: dict[Type[Model], dict[str, Subquery]] = {}

        self.exclusion: dict[str, list] = {}

        self.process_fields()

    def process_fields(self):
        # iterate over type with field names
        for model, dct in self.fields.items():

            # if Model is not already in dict, add it
            if not self.annotations.get(model, None):
                self.annotations[model] = {}

            # get name of the remote models for data comparison
            auxiliary_model: Type[Model] = self.comparison_model_enum.get_comparison_model(model)
            auxiliary_model_name: str = auxiliary_model.__name__.lower()

            # iterate over each field of certain type
            for type_name, field_names in dct.items():

                # create first starting Q for further concatenating Q of excluding for certain type
                query_conditions = Q()
                if not self.exclusion.get(type_name, None):
                    self.exclusion[type_name] = []
                for name in field_names:

                    # adding conditions of certain field for excluding
                    query_conditions.add(Q(**{f'{name}': F(f'{auxiliary_model_name}__{name}')}), Q.AND)

                    # constructing Subquery for correct seeking and further exclusion
                    core_fields: list = self.comparison_model_enum.get_core_fields(model)
                    self.annotations[model][f'{auxiliary_model_name}__{name}'] = Subquery(
                            auxiliary_model.objects
                            .filter(**{key: OuterRef(key) for key in core_fields})
                            .values(name)[:1]
                        )

                self.exclusion[type_name].append(query_conditions)

    @property
    def response(self) -> dict[str, dict | list]:
        return {
            'annotations': self.annotations,
            'exclusions': self.exclusion
        }
