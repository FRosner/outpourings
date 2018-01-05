package example

import monocle.Iso
import monocle.macros.GenLens
import org.scalatest._

class LensSpec extends FlatSpec with Matchers {

  case class Person(name: String, address: Address)
  case class Address(streetName: String, streetNumber: Int)

  "The Hello object" should "say hello" in {
    val streetNumber = GenLens[Person](_.address.streetNumber)
    val frank = Person("Frank", Address("Sun Road", 10))
    streetNumber.set(5)(frank) should be(Person("Frank", Address("Sun Road", 5)))
    frank.copy(address = frank.address.copy(streetNumber = 5)) should be(Person("Frank", Address("Sun Road", 5)))
  }
}
