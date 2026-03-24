import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Load ingredients from CSV or JSON file from /data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default='',
            help=(
                'Path to ingredients.csv or ingredients.json '
                '(optional)'
            ),
        )

    def handle(self, *args, **options):
        path_opt = options['path'].strip()

        if path_opt:
            file_path = Path(path_opt)
        else:
            candidates = (
                settings.BASE_DIR / 'data' / 'ingredients.csv',
                settings.BASE_DIR.parent / 'data' / 'ingredients.csv',
                settings.BASE_DIR / 'data' / 'ingredients.json',
                settings.BASE_DIR.parent / 'data' / 'ingredients.json',
            )
            file_path = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.exists()
                ),
                None,
            )

        if not file_path or not file_path.exists():
            raise CommandError(
                'Не найден файл ингредиентов. Передай --path '
                'или проверь папку data/.'
            )

        created = self._load_file(file_path)
        self.stdout.write(
            self.style.SUCCESS(
                'Готово. Загружено (создано/пропущено дублей): '
                f'{created} записей.'
            )
        )

    def _load_file(self, file_path: Path) -> int:
        suffix = file_path.suffix.lower()
        items = []

        if suffix == '.csv':
            with file_path.open(
                'r',
                encoding='utf-8',
            ) as source_file:
                reader = csv.reader(source_file)
                for row in reader:
                    if not row:
                        continue
                    name = row[0].strip()
                    unit = row[1].strip() if len(row) > 1 else ''
                    if name and unit:
                        items.append(
                            Ingredient(
                                name=name,
                                measurement_unit=unit,
                            )
                        )

        elif suffix == '.json':
            with file_path.open(
                'r',
                encoding='utf-8',
            ) as source_file:
                ingredients_data = json.load(source_file)

            for ingredient_data in ingredients_data:
                name = str(
                    ingredient_data.get('name', '')
                ).strip()
                unit = str(
                    ingredient_data.get('measurement_unit', '')
                ).strip()
                if name and unit:
                    items.append(
                        Ingredient(
                            name=name,
                            measurement_unit=unit,
                        )
                    )
        else:
            raise CommandError(
                'Поддерживаются только .csv и .json'
            )

        Ingredient.objects.bulk_create(
            items,
            ignore_conflicts=True,
        )
        return len(items)
