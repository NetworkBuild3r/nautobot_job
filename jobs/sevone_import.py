from nautobot.extras.models import GraphQLQuery, SecretsGroup
from nautobot.apps.jobs import Job, StringVar, IntegerVar, ObjectVar, register_jobs

class Sevone_Onboarding(Job):
    class Meta:
        name = "Device Onboarding from sevOne"
        description = "Onboards devices from SevOne by fetching and processing their details."

    sevone_api_url = StringVar(
        description="URL of the SevOne API",
        default="http://gbsasev-pas01/"
    )

    sevone_credentials = ObjectVar(
        model=SecretsGroup,
        description="SevOne API Credentials",
        display_field='name',
        default="SEVONE"
    )

    def run(self, data, commit):
        sevone_api_url = self.sevone_api_url
        sevone_credentials = self.sevone_credentials

        self.log_info(message=f"Using SevOne API URL: {sevone_api_url}")
        if sevone_credentials:
            self.log_info(message=f"Using credentials: {sevone_credentials.name}")

        if commit:
            self.log_success(message="Changes have been committed.")
        else:
            self.log_warning(message="Running in no-commit mode.")

    def check_device_exists(self, ip):
        """Check if a device with the given IP address exists in Nautobot using GraphQL."""
        query = """
        query GetDeviceByIP($ip: [String]!) {
          ip_addresses(address: $ip) {
            address
            interface_assignments {
              interface {
                device {
                  name
                }
              }
            }
          }
        }
        """
        variables = {'ip': [ip]}
        result = GraphQLQuery(query=query, variables=variables).execute()
        data = result.get('data', {}).get('ip_addresses', [])

        if data:
            self.log_info("Device found with IP {}".format(ip))
            return True
        else:
            self.log_info("No device found with IP {}".format(ip))
            return False

    def fetch_devices_from_sevone(self):
        """Fetch devices from SevOne API using credentials from a secret."""
        secret = self.sevone_credentials.get_value()  # Automatically decrypts the secret
        username, password = secret['username'], secret['password']

        creds = {'name': username, 'password': password}
        auth_response = requests.post(f"{self.sevone_api_url}/authentication/signin", json=creds,
                                      headers={'Content-Type': 'application/json'})

        if auth_response.status_code != 200:
            self.log_failure("Authentication failed!")
            return []

        token = auth_response.json()['token']
        session = requests.Session()
        session.headers.update({'Content-Type': 'application/json', 'X-AUTH-TOKEN': token})

        devices_response = session.get(f"{self.sevone_api_url}/devices?page=0&size=10000")
        if devices_response.status_code != 200:
            self.log_failure("Failed to fetch devices!")
            return []

        return devices_response.json()['content']

    def process_devices(self, devices):
        """Process each device and determine if it's missing from Nautobot."""
        missing_devices = []
        for device in devices:
            if not self.check_device_exists(device['ipAddress']):
                missing_devices.append(device)
                self.log_info(f"Device {device['name']} is missing and will be onboarded.")

        self.log_success(f"Total {len(missing_devices)} devices processed and identified for onboarding.")

register_jobs(Sevone_Onboarding)