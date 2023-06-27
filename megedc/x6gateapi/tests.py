import uuid
from django.apps import apps
from django.urls import reverse
from faker import Faker
from rest_framework import status
from rest_framework.test import APITestCase


class X6GateApiTestCase(APITestCase):

    faker = Faker()

    def test_create_gateway(self):
        client = apps.get_model('general.client').objects.create(
            name=self.faker.country(),
            currency_model_id=1
        )
        project = apps.get_model('general.project').objects.create(
            name=self.faker.country(),
            client=client
        )
        in_data = {
            "sn": self.faker.ssn(),
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            }
        }

        # Project uuid no existente
        response = self.client.post(
            reverse(
                'x6gateapi:gateway-create',
                kwargs={'project_uuid': str(uuid.uuid4())}
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Creación normal
        response = self.client.post(
            reverse(
                'x6gateapi:gateway-create',
                kwargs={'project_uuid': str(project.uuid)}
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            apps.get_model('x6gateapi.gateway').objects.filter(
                sn=in_data['sn'],
                name=in_data['name'],
                ver=in_data['ver'],
                site=in_data['site'],
                owner=in_data['owner'],
                room=in_data['room'],
            )
        )

        # Modificación
        in_data_2 = {
            "sn": in_data["sn"],
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            }
        }
        # Creación normal
        response = self.client.post(
            reverse(
                'x6gateapi:gateway-create',
                kwargs={'project_uuid': str(project.uuid)}
            ),
            in_data_2,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            apps.get_model('x6gateapi.gateway').objects.filter(
                sn=in_data_2['sn'],
                name=in_data_2['name'],
                ver=in_data_2['ver'],
                site=in_data_2['site'],
                owner=in_data_2['owner'],
                room=in_data_2['room'],
            )
        )

        # Con project inactivo
        project.enabled = False
        project.save()

        in_data["sn"] = self.faker.ssn()

        response = self.client.post(
            reverse(
                'x6gateapi:gateway-create',
                kwargs={'project_uuid': str(project.uuid)}
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_gateway(self):
        client = apps.get_model('general.client').objects.create(
            name=self.faker.country(),
            currency_model_id=1
        )
        project = apps.get_model('general.project').objects.create(
            name=self.faker.country(),
            client=client,
            currency_model_id=1
        )
        in_data = {
            "sn": self.faker.ssn(),
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            },
            "project": project
        }
        gateway = apps.get_model('x6gateapi.gateway').objects.create(
            **in_data
        )

        # Project uuid no existente
        response = self.client.get(
            reverse(
                'x6gateapi:gateway-retrieve',
                kwargs={
                    'project_uuid': str(uuid.uuid4()),
                    'sn': self.faker.ssn()
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Gateway no existente
        response = self.client.get(
            reverse(
                'x6gateapi:gateway-retrieve',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': self.faker.ssn()
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Gateway existente
        response = self.client.get(
            reverse(
                'x6gateapi:gateway-retrieve',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['sn'], in_data['sn'])
        self.assertEqual(data['name'], in_data['name'])
        self.assertEqual(data['ver'], in_data['ver'])
        self.assertEqual(data['site'], in_data['site'])
        self.assertEqual(data['owner'], in_data['owner'])
        self.assertEqual(data['room'], in_data['room'])

        # Gateway inactivo
        gateway.enabled = False
        gateway.save()
        response = self.client.get(
            reverse(
                'x6gateapi:gateway-retrieve',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Project inactivo
        gateway.enabled = True
        gateway.save()
        project.enabled = False
        project.save()
        response = self.client.get(
            reverse(
                'x6gateapi:gateway-retrieve',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_devises(self):
        client = apps.get_model('general.client').objects.create(
            name=self.faker.country(),
            currency_model_id=1
        )
        project = apps.get_model('general.project').objects.create(
            name=self.faker.country(),
            client=client,
            currency_model_id=1
        )
        gw_data = {
            "sn": self.faker.ssn(),
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            },
            "project": project
        }
        gateway = apps.get_model('x6gateapi.gateway').objects.create(
            **gw_data
        )
        in_data = {
            "device": [
                {
                    "channel": str(self.faker.random_number(digits=3)),
                    "id": str(self.faker.random_number(digits=5)),
                    "desc": self.faker.paragraph(nb_sentences=1),
                    "name": self.faker.user_name()
                },
                {
                    "channel": str(self.faker.random_number(digits=3)),
                    "id": str(self.faker.random_number(digits=3)),
                    "desc": self.faker.paragraph(nb_sentences=1),
                    "name": self.faker.user_name()
                },
            ]
        }

        # Project uuid no existente
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(uuid.uuid4()),
                    'sn': self.faker.ssn()
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Gateway no existente
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': self.faker.ssn()
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Normal
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            apps.get_model('x6gateapi.device').objects.filter(
                channel=in_data['device'][0]['channel'],
                id=in_data['device'][0]['id'],
                desc=in_data['device'][0]['desc'],
                name=in_data['device'][0]['name'],
                gateway=gateway
            )
        )
        self.assertTrue(
            apps.get_model('x6gateapi.device').objects.filter(
                channel=in_data['device'][1]['channel'],
                id=in_data['device'][1]['id'],
                desc=in_data['device'][1]['desc'],
                name=in_data['device'][1]['name'],
                gateway=gateway
            )
        )

        # change
        in_data_2 = {
            "device": [
                {
                    "channel": in_data['device'][0]['channel'],
                    "id": in_data['device'][0]['id'],
                    "desc": self.faker.paragraph(nb_sentences=1),
                    "name": self.faker.user_name()
                },
                {
                    "channel": in_data['device'][1]['channel'],
                    "id": in_data['device'][1]['id'],
                    "desc": self.faker.paragraph(nb_sentences=1),
                    "name": self.faker.user_name()
                },
            ]
        }
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data_2,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            apps.get_model('x6gateapi.device').objects.filter(
                channel=in_data_2['device'][0]['channel'],
                id=in_data_2['device'][0]['id'],
                desc=in_data_2['device'][0]['desc'],
                name=in_data_2['device'][0]['name'],
                gateway=gateway
            )
        )
        self.assertTrue(
            apps.get_model('x6gateapi.device').objects.filter(
                channel=in_data_2['device'][1]['channel'],
                id=in_data_2['device'][1]['id'],
                desc=in_data_2['device'][1]['desc'],
                name=in_data_2['device'][1]['name'],
                gateway=gateway
            )
        )

        # Gateway inactivo
        gateway.enabled = False
        gateway.save()
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data_2,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Project inactivo
        gateway.enabled = True
        gateway.save()
        project.enabled = False
        project.save()
        response = self.client.post(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data_2,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_devises(self):
        client = apps.get_model('general.client').objects.create(
            name=self.faker.country(),
            currency_model_id=1
        )
        project = apps.get_model('general.project').objects.create(
            name=self.faker.country(),
            client=client,
            currency_model_id=1
        )
        gw_data = {
            "sn": self.faker.ssn(),
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            },
            "project": project
        }
        gateway = apps.get_model('x6gateapi.gateway').objects.create(
            **gw_data
        )

        device = apps.get_model('x6gateapi.device').objects.create(
            channel=str(self.faker.random_number(digits=3)),
            id=str(self.faker.random_number(digits=5)),
            desc=self.faker.paragraph(nb_sentences=1),
            name=self.faker.user_name(),
            gateway=gateway
        )

        # Project uuid no existente
        response = self.client.get(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(uuid.uuid4()),
                    'sn': self.faker.ssn()
                }
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Gateway no existente
        response = self.client.get(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': self.faker.ssn()
                }
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Normal
        response = self.client.get(
            reverse(
                'x6gateapi:device-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        devices = response.data.get('device', [])
        self.assertEqual(len(devices), 1)
        device_data = devices[0]
        self.assertEqual(device_data['channel'], device.channel)
        self.assertEqual(device_data['id'], device.id)
        self.assertEqual(device_data['desc'], device.desc)
        self.assertEqual(device_data['name'], device.name)

    def test_create_data_node(self):
        client = apps.get_model('general.client').objects.create(
            name=self.faker.country(),
            currency_model_id=1
        )
        project = apps.get_model('general.project').objects.create(
            name=self.faker.country(),
            client=client,
            currency_model_id=1
        )
        gw_data = {
            "sn": self.faker.ssn(),
            "name": self.faker.user_name(),
            "ver": self.faker.ipv4(),
            "site": {
                "name": self.faker.country(),
                "longitude": str(self.faker.latitude()),
                "latitude": str(self.faker.longitude())
            },
            "owner": {
                "name": self.faker.user_name(),
                "desc": self.faker.paragraph(nb_sentences=1),
            },
            "room": {
                "name": self.faker.country(),
                "desc": self.faker.paragraph(nb_sentences=1),
                "camera": self.faker.city(),
            },
            "project": project
        }
        gateway = apps.get_model('x6gateapi.gateway').objects.create(
            **gw_data
        )

        device = apps.get_model('x6gateapi.device').objects.create(
            channel=str(self.faker.random_number(digits=3)),
            id=str(self.faker.random_number(digits=5)),
            desc=self.faker.paragraph(nb_sentences=1),
            name=self.faker.user_name(),
            gateway=gateway
        )

        in_data = {
            "logdt": "2016-02-19 00:05:00",
            "device": [
                {
                    "id": device.id,
                    "channel": device.channel,
                    "node": [
                        {
                            "name": self.faker.user_name(),
                            "value": str(self.faker.random_number(digits=3)),
                            "unit": self.faker.user_name(),
                            "dblink": self.faker.user_name(),
                        },
                        {
                            "name": self.faker.user_name(),
                            "value": str(self.faker.random_number(digits=3)),
                            "unit": self.faker.user_name(),
                            "dblink": self.faker.user_name(),
                        }
                    ]
                }
            ]
        }

        # Project uuid no existente
        response = self.client.post(
            reverse(
                'x6gateapi:rtdata-create',
                kwargs={
                    'project_uuid': str(uuid.uuid4()),
                    'sn': self.faker.ssn()
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Gateway no existente
        response = self.client.post(
            reverse(
                'x6gateapi:rtdata-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': self.faker.ssn()
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Normal
        response = self.client.post(
            reverse(
                'x6gateapi:rtdata-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            apps.get_model('x6gateapi.DataNone').objects.filter(
                name=in_data['device'][0]['node'][0]['name'],
                value=in_data['device'][0]['node'][0]['value'],
                unit=in_data['device'][0]['node'][0]['unit'],
                dblink=in_data['device'][0]['node'][0]['dblink'],
                data__logdt=in_data['logdt'],
                device=device,
                discard=True
            )
        )
        self.assertTrue(
            apps.get_model('x6gateapi.DataNone').objects.filter(
                name=in_data['device'][0]['node'][1]['name'],
                value=in_data['device'][0]['node'][1]['value'],
                unit=in_data['device'][0]['node'][1]['unit'],
                dblink=in_data['device'][0]['node'][1]['dblink'],
                data__logdt=in_data['logdt'],
                device=device,
                discard=True
            )
        )

        # Device ready
        device.ready = True
        device.save()

        in_data = {
            "logdt": "2016-02-19 00:10:00",
            "device": [
                {
                    "id": device.id,
                    "channel": device.channel,
                    "node": [
                        {
                            "name": self.faker.user_name(),
                            "value": str(self.faker.random_number(digits=3)),
                            "unit": self.faker.user_name(),
                            "dblink": self.faker.user_name(),
                        },
                        {
                            "name": self.faker.user_name(),
                            "value": str(self.faker.random_number(digits=3)),
                            "unit": self.faker.user_name(),
                            "dblink": self.faker.user_name(),
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse(
                'x6gateapi:rtdata-create',
                kwargs={
                    'project_uuid': str(project.uuid),
                    'sn': gateway.sn
                }
            ),
            in_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            apps.get_model('x6gateapi.DataNone').objects.filter(
                name=in_data['device'][0]['node'][0]['name'],
                value=in_data['device'][0]['node'][0]['value'],
                unit=in_data['device'][0]['node'][0]['unit'],
                dblink=in_data['device'][0]['node'][0]['dblink'],
                data__logdt=in_data['logdt'],
                device=device,
                discard=False
            )
        )
        self.assertTrue(
            apps.get_model('x6gateapi.DataNone').objects.filter(
                name=in_data['device'][0]['node'][1]['name'],
                value=in_data['device'][0]['node'][1]['value'],
                unit=in_data['device'][0]['node'][1]['unit'],
                dblink=in_data['device'][0]['node'][1]['dblink'],
                data__logdt=in_data['logdt'],
                device=device,
                discard=False
            )
        )
