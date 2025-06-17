from requests import Request

from vinetrimmer.utils.BamSDK.services import Service


# noinspection PyPep8Naming
class account(Service):
    def createAccountGrant(self, json: dict, access_token: str) -> dict:
        endpoint = self.client.endpoints["createAccountGrant"]
        return self.session.request(
            method=endpoint.method,
            url=endpoint.href,
            headers=endpoint.get_headers(accessToken=access_token),
            json=json,
        ).json()

    def getUserProfiles(self, access_token: str) -> dict:
        endpoint = self.client.endpoints["getCurrentAccount"]
        return self.session.request(
            method=endpoint.method,
            url=endpoint.href,
            headers=endpoint.get_headers(accessToken=access_token),
        ).json()

    def setActiveUserProfile(self, profile_id: str, access_token: str) -> dict:
        # Hardcoded since its not in v4 anymore
        return self.session.put(
            url=f"https://disney.api.edge.bamgrid.com/accounts/me/active-profile/{profile_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
